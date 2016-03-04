import json
import time
import random

from django import http
from django.template.response import TemplateResponse
from django.core.cache import cache
from moneywagon import get_address_balance, guess_currency_from_address, ALL_SERVICES

from .utils import make_crypto_data_json, make_service_info_json, service_modes

services_by_id = {s.service_id: s for s in ALL_SERVICES}
crypto_data_json = make_crypto_data_json()
service_info_json = make_service_info_json()

def perform_lookup(request, currency, service_mode, service_id):
    """
    Passes on this request to the API, then return their response normalized to
    a single API.
    """
    if service_mode not in service_modes:
        raise Exception("Unknown service mode")

    include_raw = request.GET.get('include_raw', False)
    Service = services_by_id[int(service_id)]

    if service_mode == "address_balance":
        address = request.GET['address']
        cache_key = '%s:%s:%s' % (service_mode, service_id, address)
        hit = cache.get(cache_key)

        if hit:
            time.sleep(random.random() * 2) # simulate external call
            response_dict = hit
            response_dict['cache_hit'] = True
        else:
            try:
                s = Service()
                response_dict = {
                    'balance': s.get_balance(currency, address),
                    'url': s.last_url,
                    'raw_response': s.last_raw_response.json(),
                    'timestamp': time.time(),
                    'service_name': Service.name
                }
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
    })


def block_lookup(request):
    pass

def supported_services(request):
    pass
