import datetime
import json
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.contrib.auth import authenticate, login as init_login
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
from django.template.response import TemplateResponse
from django import http

from .models import WalletMasterKeys, FailedLogin, AUTO_LOGOUT_CHOICES
from multiexplorer.utils import get_wallet_currencies

crypto_data = get_wallet_currencies()
crypto_data_json = json.dumps(crypto_data)

from multiexplorer.views import _cached_fetch

def get_rates(fiat):
    rates = {}
    for data in crypto_data:
        services, response = _cached_fetch(
            service_mode="current_price",
            service_id="fallback",
            fiat=fiat,
            currency=data['code'],
            currency_name=data['name']
        )

        rates[data['code']] = {
            'rate': response['current_price'],
            'provider': response['service_name']
        }
    return rates

def home(request):
    return TemplateResponse(request, "wallet_home.html", {
        'crypto_data_json': crypto_data_json,
        'crypto_data': crypto_data,
        'supported_fiats': settings.WALLET_SUPPORTED_FIATS,
        'autologout_choices': AUTO_LOGOUT_CHOICES
    })


@csrf_exempt
def save_settings(request):
    wallet = WalletMasterKeys.objects.get(user=request.user)
    new_fiat = request.POST['display_fiat']
    previous_fiat = wallet.display_fiat
    wallet.display_fiat = new_fiat
    wallet.auto_logout = request.POST['auto_logout']
    wallet.show_wallet_list = request.POST['show_wallet_list']
    wallet.save()

    resp = {
        'settings': wallet.get_settings()
    }

    if previous_fiat != new_fiat:
        resp['exchange_rates'] = get_rates(new_fiat),

    return http.JsonResponse(resp)


def register_new_wallet_user(request):
    encrypted_mnemonic = request.POST['encrypted_mnemonic']
    password = request.POST['password']
    username = request.POST['username']

    user = User.objects.create(
        username=username,
        email=request.POST.get('email', ''),
    )
    user.set_password(password)
    user.save()

    wal = WalletMasterKeys.objects.create(
        user=user, encrypted_mnemonic=encrypted_mnemonic
    )

    user = authenticate(username=username, password=password)
    init_login(request, user)

    return http.JsonResponse({
        'wallet_settings': wal.get_settings(),
        'exchange_rates': get_rates(wal.display_fiat),
    })


def login(request):
    """
    Authenticate the user. On failed attempts, record the event, and limit
    5 failed attempts every 15 minutes.
    """
    username = request.POST['username']
    password = request.POST['password']

    fithteen_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes=15)
    tries = FailedLogin.objects.filter(username=username, time__gt=fithteen_minutes_ago)
    try_count = tries.count()

    if try_count < 5:
        user = authenticate(username=username, password=password)

        if user and user.is_authenticated():
            init_login(request, user)
            wal = WalletMasterKeys.objects.get(user=request.user)

            return http.JsonResponse({
                'encrypted_mnemonic': wal.encrypted_mnemonic,
                'wallet_settings': wal.get_settings(),
                'exchange_rates': get_rates(wal.display_fiat),
            })
        else:
            FailedLogin.objects.create(username=username)
            tries_left = 5 - try_count
            return http.JsonResponse({"tries_left": tries_left}, status=401)

    time_of_next_try = tries.latest().time + datetime.timedelta(minutes=15)
    minutes_to_wait = (time_of_next_try - timezone.now()).total_seconds() / 60.0
    return http.JsonResponse({"login_timeout": "Try again in %.1f minutes." % minutes_to_wait}, status=401)
