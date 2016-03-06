import json
import time
import random

from django import http
from django.template.response import TemplateResponse
from django.core.cache import cache
from django.conf import settings

from moneywagon import get_address_balance, guess_currency_from_address, ALL_SERVICES

from .utils import make_crypto_data_json, make_service_info_json, service_modes, get_block_currencies

services_by_id = {s.service_id: s for s in ALL_SERVICES}
crypto_data_json = make_crypto_data_json()
service_info_json = make_service_info_json()
block_info_currencies = get_block_currencies()

def perform_lookup(request, currency, service_mode, service_id):
    """
    Passes on this request to the API, then return their response normalized to
    a single API.
    """
    if service_mode not in service_modes:
        raise Exception("Unknown service mode")

    include_raw = request.GET.get('include_raw', False)
    Service = services_by_id[int(service_id)]

    address = request.GET.get('address', None)
    latest = request.GET.get('latest', False)
    block_hash = request.GET.get("block_hash", None)
    block_number = request.GET.get("block_number", None)

    key_ending = address or latest or block_hash or block_number

    cache_key = '%s:%s:%s:%s' % (currency.lower(), service_mode, service_id, key_ending)
    hit = cache.get(cache_key)

    if hit:
        time.sleep(random.random() * 2) # simulate external call
        response_dict = hit
        response_dict['cache_hit'] = True
    else:
        try:
            s = Service()
            if service_mode == 'address_balance':
                response_dict = {
                    'balance': s.get_balance(currency, address)
                }
            elif service_mode == 'unspent_outputs':
                utxos = s.get_unspent_outputs(currency, address)
                response_dict = {
                    'utxos': sorted(utxos, key=lambda x: x['output'])
                }
            elif service_mode == 'historical_transactions':
                txs = s.get_histrical_transactions(currency, address)
                response_dict = {
                    'transactions': sorted(txs, key=lambda x: -x['confirmations'])
                }
            elif service_mode == 'get_block':
                response_dict = {
                    'block': s.get_block(
                        currency, latest=latest, block_height=block_height, block_number=block_number
                    )
                }
            elif service_mode == 'get_optimal_fee':
                response_dict = {
                    'optimal_fee_per_KiB': s.get_optimal_fee(currency, 1024)
                }

            response_dict.update({
                'url': s.last_url,
                'raw_response': s.last_raw_response.json(),
                'timestamp': int(time.time()),
                'service_name': Service.name
            })

        except Exception as exc:
            return http.JsonResponse(
                {'error': "%s: %s" % (exc.__class__.__name__, str(exc))
            }, status=500)

        cache.set(cache_key, response_dict)
        response_dict['cache_hit'] = False

    if not include_raw:
        del response_dict['raw_response']

    return http.JsonResponse(response_dict)

def home(request):
    return TemplateResponse(request, "home.html", {
        'crypto_data_json': crypto_data_json,
        'service_info_json': service_info_json,
        'block_info_currencies': block_info_currencies,
        'TEST_ADDRESS': settings.TEST_ADDRESS
    })


def block_lookup(request):
    pass

def supported_services(request):
    pass
