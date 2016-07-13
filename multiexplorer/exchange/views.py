import json

from django.template.response import TemplateResponse
from django import http
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect

try:
    from models import ExchangeCurrency, ExchangeAddress
except ImportError:
    from .models import ExchangeCurrency, ExchangeAddress

from multiexplorer.utils import get_wallet_currencies

crypto_data = get_wallet_currencies()
crypto_data_json = json.dumps(crypto_data)


def home(request):
    return TemplateResponse(request, "exchange_home.html", {
        'supported_cryptos': ExchangeCurrency.objects.all(),
        'crypto_data': crypto_data_json,
        'ENABLE_EXCHANGE': settings.ENABLE_EXCHANGE
    })


@csrf_exempt
def create_exchange(request):
    if request.method == "POST":
        deposit_code = request.POST['deposit_code']
        withdraw_address = request.POST['withdraw_address']
        withdraw_code = request.POST['withdraw_code']
        error = None

        try:
            withdraw_currency = ExchangeCurrency.get_active(code=withdraw_code)
        except ExchangeCurrency.DoesNotExist as exc:
            error = 'withdraw'
            error_msg = exc.__str__

        try:
            deposit_currency = ExchangeCurrency.get_active(code=deposit_code)
        except ExchangeCurrency.DoesNotExist as exc:
            error = 'deposit'
            error_msg = exc.__str__

        if error:
            return http.JsonResponse({
                'error': error_msg
            }, status=400)

        exchange, created = ExchangeAddress.objects.get_or_create(
            deposit_currency=deposit_currency,
            withdraw_address=withdraw_address,
            withdraw_currency=withdraw_currency
        )
        exchange.kick()

        return http.JsonResponse({
            'deposit_address': exchange.deposit_address,
            'exchange_rate': exchange.exchange_rate,
            'seconds_left': exchange.seconds_to_needing_kick(),
        })
    else:
        return redirect("exchange")
