import json
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.contrib.auth import authenticate, login as init_login
from django.contrib.auth.models import User
from django.conf import settings
from django.template.response import TemplateResponse
from django import http

from .models import WalletMasterKeys, AUTO_LOGOUT_CHOICES
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
        'exchange_rates': rates,
        'supported_fiats': settings.WALLET_SUPPORTED_FIATS,
        'supported_cryptos': settings.WALLET_SUPPORTED_CRYPTOS,
        'autologout_choices': AUTO_LOGOUT_CHOICES
    })


@csrf_exempt
def save_settings(request):
    wallet = WalletMasterKeys.objects.get(user=request.user)
    wallet.display_fiat = request.POST['display_fiat']
    wallet.auto_logout = request.POST['auto_logout']
    wallet.show_wallet_list = request.POST['show_wallet_list']
    wallet.save()
    return http.HttpResponse("OK")


def register_new_wallet_user(request):
    encrypted_mnemonic = request.POST['encrypted_mnemonic']

    user = User.objects.create(
        username=request.POST['username'],
        email=request.POST.get('email', ''),
    )
    user.set_password(request.POST['password'])
    user.save()

    wal = WalletMasterKeys.objects.create(
        user=user, encrypted_mnemonic=encrypted_mnemonic
    )

    return http.JsonResponse({
        'wallet_settings': wal.get_settings(),
    })


def login(request):
    username = request.POST['username']
    password = request.POST['password']

    user = authenticate(username=username, password=password)

    if user and user.is_authenticated():
        init_login(request, user)
        wal = WalletMasterKeys.objects.get(user=request.user)

        return http.JsonResponse({
            'encrypted_mnemonic': wal.encrypted_mnemonic,
            'wallet_settings': wal.get_settings(),
        })

    return http.HttpResponse("Invalid Login", status=403)
