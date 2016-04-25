import json
from django.contrib.auth import authenticate, login as init_login
from django.contrib.auth.models import User
from django.template.response import TemplateResponse
from django import http

from .models import WalletMasterKeys
from multiexplorer.utils import get_wallet_currencies

crypto_data = get_wallet_currencies()
crypto_data_json = json.dumps(crypto_data)

from multiexplorer.views import _cached_fetch

def home(request):

    rates = {}
    for data in crypto_data:
        services, response = _cached_fetch(
            service_mode="current_price",
            service_id="fallback",
            fiat='usd',
            currency=data['code'],
            currency_name=data['name']
        )

        rates[data['code']] = {
            'rate': response['current_price'],
            'provider': response['service_name']
        }

    return TemplateResponse(request, "wallet_home.html", {
        'crypto_data_json': crypto_data_json,
        'crypto_data': crypto_data,
        'exchange_rates': rates
    })


def register_new_wallet_user(request):
    encrypted_mnemonic = request.POST['encrypted_mnemonic']

    user = User.objects.create(
        username=request.POST['username'],
        email=request.POST.get('email', ''),
    )
    user.set_password(request.POST['password'])
    user.save()

    WalletMasterKeys.objects.create(
        user=user, encrypted_mnemonic=encrypted_mnemonic
    )

    return http.HttpResponse("OK")


def login(request):
    username = request.POST['username']
    password = request.POST['password']

    user = authenticate(username=username, password=password)

    if user and user.is_authenticated():
        init_login(request, user)
        seed = WalletMasterKeys.objects.get(user=request.user)

        return http.JsonResponse({
            'encrypted_mnemonic': seed.encrypted_mnemonic
        })

    return http.HttpResponse("Invalid Login", status=403)
