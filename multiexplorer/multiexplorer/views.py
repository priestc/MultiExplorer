import json
import time
import random

from django import http
from django.template.response import TemplateResponse
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.conf import settings

from moneywagon import (
    service_table, get_address_balance, guess_currency_from_address, ALL_SERVICES,
    get_unspent_outputs, get_historical_transactions, get_optimal_fee, get_block,
    get_single_transaction
)

from moneywagon.crypto_data import crypto_data

from .utils import (
    make_crypto_data_json, make_service_info_json, service_modes,
    get_block_currencies, get_balance_currencies
)

from .models import CachedTransaction

services_by_id = {s.service_id: s for s in ALL_SERVICES}
crypto_data_json = make_crypto_data_json()
service_info_json = make_service_info_json()
block_info_currencies = get_block_currencies()
service_table_html = service_table(format='html')

from moneywagon.services import ThisIsVTC, ReddcoinCom
ThisIsVTC.protocol = 'http'
ReddcoinCom.protocol = 'http'

def perform_lookup(request, service_mode, service_id):
    """
    Passes on this request to the API, then return their response normalized to
    a single API. service_mode == (address_balance, historical_transactions)
    """
    include_raw = request.GET.get('include_raw', False)

    extended_fetch = (
        request.GET.get('extended_fetch', 'false') == 'true' and
        service_mode == 'historical_transactions'
    )

    paranoid = service_id.startswith("paranoid")
    average_mode = service_id.startswith("average")
    private_mode = service_id.startswith("private")

    if service_id == "fallback" or paranoid or average_mode or private_mode:
        Service = None
    else:
        try:
            Service = services_by_id[int(service_id)]
        except IndexError:
            return http.JsonResponse({
                'error': "Unknown Service ID: %s. This service may have been decomissioned." % service_id
            }, status=400)

    address = request.GET.get('address', None)
    addresses = request.GET.get('addresses', [])
    xpub = request.GET.get('xpub', None)

    block_args = {
        'latest': request.GET.get('latest', ''),
        'block_hash': request.GET.get("block_hash", ''),
        'block_number': request.GET.get("block_number", '')
    }

    currency = request.GET.get("currency", None)
    if not currency:
        try:
            guess_currency_result = guess_currency_from_address(address)
        except ValueError as exc:
            return http.JsonResponse({'error': str(exc)}, status=400)

        if len(guess_currency_result) == 1:
            currency, currency_name = guess_currency_result[0]
        else:
            msg = "Address may be one of %s, please specify which one by using the crypto parameter" % (
                ', '.join([x[0] for x in guess_currency_result])
            )
            return http.JsonResponse({'error': msg}, status=400)
    else:
        currency_name = crypto_data[currency]['name']
        currency = currency.lower()

    if not currency:
        return http.JsonResponse({
            'error': "Currency Not Recognized: %s" % currency_name
        }, status=400)

    errors, response_dict = _cached_fetch(**locals())
    if errors:
        return http.JsonResponse(response_dict, status=500)

    return http.JsonResponse(response_dict)


def _cached_fetch(service_mode, service_id, address, addresses, xpub, currency, currency_name, include_raw=False, Service=None, block_args=None, **k):
    key_ending = address or ":".join(block_args.values()) or xpub or ','.join(addresses)

    eh = k['extended_fetch']
    if eh:
        key_ending += "--ExtendedFetch"

    cache_key = '%s:%s:%s:%s' % (currency.lower(), service_mode, service_id, key_ending)
    hit = cache.get(cache_key)

    if hit:
        response_dict = hit
    else:
        #try:
        response_dict = _make_moneywagon_fetch(**locals())
        if eh:
            response_dict = _do_extended_fetch(currency, response_dict)

        #except Exception as exc:
        #    return True, {'error': "%s: %s" % (exc.__class__.__name__, str(exc))}

        response_dict.update({
            'timestamp': int(time.time()),
            'currency': [currency, currency_name]
        })

        cache.set(cache_key, response_dict)

    if not include_raw:
        response_dict.pop('raw_response', None)
        services = response_dict.get('services', [])
        if services:
            response_dict['services'] = [
                {'name': x['name'], 'id': x['id']} for x in services
            ]

    response_dict['fetched_seconds_ago'] = int(time.time()) - response_dict['timestamp']
    del response_dict['timestamp']
    return None, response_dict


def _make_moneywagon_fetch(Service, service_mode, service_id, address, addresses, xpub, currency, currency_name, block_args, **k):
    if Service:
        if currency not in Service.supported_cryptos:
            raise Exception("%s not supported for %s with %s" % (
                currency_name, service_mode, Service.name
            ))
        services = [Service]
    else:
        services = [] # fallback mode

    modes = dict(
        report_services=True,
        services=services,
    )

    if service_id.startswith("paranoid"):
        modes['paranoid'] = int(service_id[8:])
    elif service_id.startswith("average"):
        modes['average'] = int(service_id[7:])
    elif service_id.startswith("private"):
        modes['private'] = int(service_id[7:])
        if modes['private'] > 30:
            raise Exception("Private mode maximum of 30")

    if address:
        modes['address'] = address
    elif addresses:
        modes['addresses'] = addresses.split(',')

    if service_mode == 'address_balance':
        used_services, balance = get_address_balance(currency, **modes)
        ret = {'balance': balance}
    elif service_mode == 'unspent_outputs':
        used_services, utxos = get_unspent_outputs(currency, **modes)
        ret = {'utxos': sorted(utxos, key=lambda x: x['output'])}
    elif service_mode == 'historical_transactions':
        used_services, txs = get_historical_transactions(currency, **modes)
        ret = {'transactions': sorted(txs, key=lambda x: x['txid'])}
    elif service_mode == 'get_block':
        modes.update(block_args)
        used_services, block_data = get_block(currency, **modes)
        ret = {'block': block_data}
    elif service_mode == 'get_optimal_fee':
        used_services, fee = get_optimal_fee(currency, 1024, **modes)
        ret = {'optimal_fee_per_KiB': fee}
    else:
        raise Exception("Unsupported Service mode")

    if not used_services:
        pass # private mode does not return services
    elif len(used_services) == 1:
        s = used_services[0]
        if s:
            ret['url'] = s.last_url
            ret['raw_response'] = s.last_raw_response.json()
            ret['service_name'] = s.name
            ret['service_id'] = s.service_id
    else:
        ret['services'] = [
            {'name': s.name, 'id': s.service_id, 'raw_response': s.last_raw_response.json()}
            for s in used_services
        ]

    return ret

def _do_extended_fetch(crypto, response):
    txs = []
    for tx in response['transactions']:
        full_tx = CachedTransaction.fetch_full_tx(crypto, txid=tx['txid'])
        txs.append(full_tx)

    return {'transactions': txs}


def home(request):
    return TemplateResponse(request, "home.html", {
        'supported_currencies': get_balance_currencies,
        'block_info_currencies': block_info_currencies,
        'TEST_ADDRESS': settings.TEST_ADDRESS,
    })


def single_address(request, address):
    currency = request.GET.get('currency', None)

    if not currency:
        try:
            guess_currency_result = guess_currency_from_address(address)
        except Exception as exc:
            return TemplateResponse(request, "single_address.html", {
                'crypto_data_json': crypto_data_json,
                'service_info_json': service_info_json,
                'address': address,
                'currency': None,
                'transactions': [],
                'currency_name': None,
                'currency_icon': None,
            })

        if len(guess_currency_result) == 1:
            currency, currency_name = guess_currency_result[0]
        else:
            return http.HttpResponseRedirect(
                reverse("address_disambiguation", kwargs={'address': address})
            )
    else:
        currency = currency.lower()
        crypto_name = currency_name = crypto_data[currency]['name']

    error, response = _cached_fetch(
        currency=currency, currency_name=currency_name, service_id="fallback",
        address=address, Service=None, service_mode="historical_transactions"
    )

    if not error:
        txs = response['transactions']
    else:
        txs = []

    return TemplateResponse(request, "single_address.html", {
        'crypto_data_json': crypto_data_json,
        'service_info_json': service_info_json,
        'address': address,
        'currency': currency,
        'transactions': txs,
        'currency_name': currency_name,
        'currency_icon': "logos/" + currency.lower() + "-logo.png",
    })


def block_lookup(request):
    return TemplateResponse(request, "block_lookup.html", {
        'crypto_data_json': crypto_data_json,
        'service_info_json': service_info_json,
        'block_info_currencies': block_info_currencies,
        'currency': request.GET.get('currency', None),
        'block_hash': request.GET.get("block_hash", None),
        'block_number': request.GET.get("block_number", None)
    })


def api_docs(request):
    return TemplateResponse(request, 'api_docs.html', {
        'service_table': service_table_html,
        'domain': "multiexplorer.com",
    })

def address_disambiguation(request, address):
    """
    When the user tried to lookup a currency that has a duplicate address byte
    take them to this page where they can choose which currency they meant.
    """
    guess_currency_result = guess_currency_from_address(address)
    balances = {}
    for crypto, name in guess_currency_result:
        try:
            balance = get_address_balance(crypto, address)
        except Exception as exc:
            balance = str(exc)

        balances[crypto.upper()] = {'balance': balance, 'name': name}

    return TemplateResponse(request, "address_disambiguation.html", {
        'balances': balances,
        'address': address,
    })
