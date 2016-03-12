import json
import time
import random

from django import http
from django.template.response import TemplateResponse
from django.core.cache import cache
from django.conf import settings

from moneywagon import (
    service_table, get_address_balance, guess_currency_from_address, ALL_SERVICES,
    get_unspent_outputs, get_historical_transactions, get_optimal_fee, get_block
)

from moneywagon.crypto_data import crypto_data

from .utils import make_crypto_data_json, make_service_info_json, service_modes, get_block_currencies

services_by_id = {s.service_id: s for s in ALL_SERVICES}
crypto_data_json = make_crypto_data_json()
service_info_json = make_service_info_json()
block_info_currencies = get_block_currencies()

def perform_lookup(request, service_mode, service_id):
    """
    Passes on this request to the API, then return their response normalized to
    a single API.
    """
    include_raw = request.GET.get('include_raw', False)

    if service_id == "fallback" or service_id.startswith("paranoid") or service_id.startswith("average"):
        Service = None
    else:
        try:
            Service = services_by_id[int(service_id)]
        except IndexError:
            return http.JsonResponse({
                'error': "Unknown Service ID: %s. This service may have been decomissioned." % service_id
            }, status=400)

    address = request.GET.get('address', None)

    block_args = {
        'latest': request.GET.get('latest', ''),
        'block_hash': request.GET.get("block_hash", ''),
        'block_number': request.GET.get("block_number", '')
    }

    currency = request.GET.get("currency", None)
    if not currency:
        currency, currency_name = guess_currency_from_address(address)
    else:
        currency_name = crypto_data[currency]['name']
        currency = currency.lower()

    if not currency:
        return http.JsonResponse({
            'error': "Currency Not Recognized: %s" % currency_name
        }, status=400)

    key_ending = address or ":".join(block_args.values())

    cache_key = '%s:%s:%s:%s' % (currency.lower(), service_mode, service_id, key_ending)
    hit = cache.get(cache_key)

    if hit:
        #time.sleep(random.random() * 2) # simulate external call
        response_dict = hit
    else:
        try:
            response_dict = _make_moneywagon_fetch(**locals())
        except Exception as exc:
            return http.JsonResponse(
                {'error': "%s: %s" % (exc.__class__.__name__, str(exc))
            }, status=500)

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

    return http.JsonResponse(response_dict)


def _make_moneywagon_fetch(Service, service_mode, service_id, address, currency, currency_name, block_args, **k):
    if Service:
        if currency not in Service.supported_cryptos:
            raise Exception("%s not supported for %s with %s" % (
                currency_name, service_mode, serv.name
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

    if service_mode == 'address_balance':
        used_services, balance = get_address_balance(currency, address, **modes)
        ret = {'balance': balance}
    elif service_mode == 'unspent_outputs':
        used_services, utxos = get_unspent_outputs(currency, address, **modes)
        ret = {'utxos': sorted(utxos, key=lambda x: x['output'])}
    elif service_mode == 'historical_transactions':
        used_services, txs = get_historical_transactions(currency, address, **modes)
        ret = {'transactions': sorted(txs, key=lambda x: -x['confirmations'])}
    elif service_mode == 'get_block':
        modes.update(block_args)
        used_services, block_data = get_block(currency, **modes)
        ret = {'block': block_data}
    elif service_mode == 'get_optimal_fee':
        used_services, fee = get_optimal_fee(currency, 1024, **modes)
        ret = {'optimal_fee_per_KiB': fee}
    else:
        raise Exception("Unsupported Service mode")

    if len(used_services) == 1:
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


def home(request):
    return TemplateResponse(request, "home.html", {
        'crypto_data_json': crypto_data_json,
        'service_info_json': service_info_json,
        'block_info_currencies': block_info_currencies,
        'TEST_ADDRESS': settings.TEST_ADDRESS,
    })


def single_address(request, address):
    currency, currency_name = guess_currency_from_address(address)

    return TemplateResponse(request, "single_address.html", {
        'crypto_data_json': crypto_data_json,
        'service_info_json': service_info_json,
        'address': address,
        'currency': currency,
        'currency_name': currency_name,
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
        'service_table': service_table(format='html'),
        'domain': "multiexplorer.com",
    })
