import json

from django.http import HttpResponse
import arrow
from models import PriceTick

# Create your views here.
def price_for_date(request):
    crypto_symbol = request.GET['crypto']
    fiat_symbol = request.GET['fiat']
    date = arrow.get(request.GET['date']).datetime
    tick = PriceTick.objects.filter(
        date__gt=date,
        currency__iexact=crypto_symbol,
    ).order_by('date')[0]

    j = json.dumps([tick.price, tick.exchange, tick.date.isoformat()])
    return HttpResponse(j, content_type="application/json")
