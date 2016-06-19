from django.template.response import TemplateResponse
from django import http
from models import ExchangeCurrency

def home(request):
    return TemplateResponse(request, "exchange_home.html", {})

def create_exchange(request):
    deposit_crypto = request.POST['deposit_code']
    withdraw_address = request.POST['withdraw_address']

    deposit_currency = ExchangeCurrency.objects.filter(code=deposit_crypto)
    exchange, created = ExchangeAdress.objects.get_or_create(
        deposit_currency=deposit_currency,
        withdraw_address=withdraw_address
    )
    exchange.kick()

    return http.JsonResponse({
        'deposit_address': exchange.withdraw_address,
        'exchange_rate': exchange.exchange_rate,
        'seconds_left': exchange.seconds_to_needing_kick(),
    })
