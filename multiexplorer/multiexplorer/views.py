import json
from django import http
from django.template.response import TemplateResponse

from moneywagon import get_address_balance, guess_currency_from_address, ALL_SERVICES

from .utils import make_crypto_data_json, make_service_info_json

services_by_id = {s.service_id: s for s in ALL_SERVICES}

crypto_data_json = make_crypto_data_json()
service_info_json = make_service_info_json()

def perform_lookup(request, service_tag, service_id, payload):

    Service = services_by_id[service_id]

    if service_tag == "address_balance":
        address = request.POST['address']
        currency = guess_currency_from_address(address)
        baance = Service().get_balance(currency, address)

        return http.JsonResponse({
            'balance': balance
        })

def home(request):
    return TemplateResponse(request, "home.html", {
        'crypto_data_json': crypto_data_json,
        'service_info_json': service_info_json,
    })


def block_lookup(request):
    pass

def supported_services(request):
    pass
