from __future__ import print_function

import calendar
import datetime
import csv
import os
import gzip

import arrow
import requests
import pytz

from django.db import models
from django.conf import settings
from django.utils import timezone
from multiexplorer.utils import get_wallet_currencies

from moneywagon import get_current_price

class PriceTick(models.Model):
    currency = models.CharField(max_length=8) # btc/ltc/doge/etc.
    exchange = models.CharField(max_length=128) # kraken/bitstamp/etc.
    base_fiat = models.CharField(max_length=8) # USD/EUR/GBP/etc.
    date = models.DateTimeField(db_index=True)
    price = models.FloatField()

    def __unicode__(self):
        return "%s %s %s->%s" % (self.date, self.price, self.currency, self.base_fiat)

    @classmethod
    def nearest(cls, crypto, fiat, date):
        """
        Find the tick nearest the passed in date. May raise DoesNotExist
        if a value can't be found.
        """
        try:
            match = cls.objects.filter(
                currency__iexact=crypto, base_fiat__iexact=fiat, date__lt=date
            ).latest()
            return {
                'price': match.price, 'source': match.exchange,
                'time': match.date, 'fiat': fiat
            }
        except cls.DoesNotExist:
            fiat_btc = cls.objects.filter(
                currency__iexact=crypto, base_fiat__iexact='BTC', date__lt=date
            ).latest()
            crypto_btc = cls.objects.filter(
                currency__iexact='btc', base_fiat__iexact=fiat, date__lt=date
            ).latest()
            return {
                'price': fiat_btc.price * crypto_btc.price,
                'source': "%s->%s" % (fiat_btc.exchange, crypto_btc.exchange),
                'time': crypto_btc.date,
                'fiat': fiat
            }

    @classmethod
    def get_current_price(cls, crypto, fiat, verbose=False):
        price = cls.get_non_stale_price(crypto, fiat)
        if price:
            return price
        sources, price = get_current_price(crypto, fiat, report_services=True, verbose=verbose)
        tick = cls.record_price(price, crypto, fiat, sources[0].name)
        return tick

    @classmethod
    def record_price(cls, price, crypto, fiat, source_name, at_time=None, interval=None):
        """
        If you already have the price data and want to record that, use this method.
        WIll only record if the current price is within PRICE_INTERVAL_SECONDS.
        """
        at_time = at_time or timezone.now()
        if cls.needs_update(crypto, fiat, at_time, interval):
            obj = cls.objects.create(
                date=at_time,
                price=price,
                base_fiat=fiat.upper(),
                currency=crypto.upper(),
                exchange=source_name
            )
            return obj
        return False

    @classmethod
    def get_non_stale_price(cls, crypto, fiat, at_time=None, interval=None):
        at_time = at_time or timezone.now()
        try:
            kwargs = {
                'currency__iexact': crypto,
                'base_fiat__iexact': fiat,
                'date__lte': at_time
            }
            if interval:
                kwargs['date__gte'] = at_time - interval
            price = cls.objects.filter(**kwargs).latest()
        except cls.DoesNotExist:
            return None

        if price.is_stale(at_time, interval):
            return None

        return price


    @classmethod
    def needs_update(cls, crypto, fiat, at_time=None, interval=None):
        at_time = at_time or timezone.now()
        price = cls.get_non_stale_price(crypto, fiat, at_time, interval)
        return price is None

    def is_stale(self, at_time=None, interval=None):
        interval = interval or datetime.timedelta(seconds=settings.PRICE_INTERVAL_SECONDS)
        at_time = at_time or timezone.now()
        interval_ago = at_time - interval
        return self.date < interval_ago

    class Meta:
        get_latest_by = 'date'


def load_from_bitcoincharts(tag, source_name, crypto, fiat):
    from clint.textui import progress

    interval = datetime.timedelta(hours=1)
    path = os.path.join(os.path.expanduser("~"), tag + ".csv.gz")

    if not os.path.isfile(path):
        print("Downloading ~/%s.csv.gz" % tag)
        r = requests.get("http://api.bitcoincharts.com/v1/csv/%s.csv.gz" % tag, stream=True)
        with open(path, 'wb') as f:
            total_length = int(r.headers.get('content-length'))
            for chunk in progress.bar(r.iter_content(chunk_size=1024), expected_size=(total_length/1024) + 1):
                if chunk:
                    f.write(chunk)
                    f.flush()
    else:
        print("Skipping download of ~/%s.csv.gz" % tag)


    with gzip.open(path) as f:
        last_tick = None
        for i, line in enumerate(f.readlines()):
            timestamp, price, volume = line.split(",")
            tick_date = datetime.datetime.fromtimestamp(int(timestamp)).replace(tzinfo=pytz.UTC)

            if last_tick and (tick_date - last_tick) < interval:
                continue

            p = PriceTick.record_price(
                price=price, crypto=crypto,
                fiat=fiat, source_name=source_name,
                at_time=tick_date,
                interval=interval
            )

            if p:
                print("made:", p)
                last_tick = tick_date


def load_all():
    load_from_bitcoincharts('bitstampUSD', "Bitstamp", 'BTC', 'USD')
    load_from_bitcoincharts('btceRUR', "BTCe", 'BTC', 'RUR')
    load_from_bitcoincharts('coincheckJPY', 'coincheck', 'BTC', 'JPY')
    load_quandl_v3('BTER/BTCCNY', 'BTC', 'CNY')
    load_quandl_v3('GDAX/EUR', 'BTC', 'EUR')

    load_quandl_v3('BTER/VTCBTC', 'VTC', 'BTC')
    load_quandl_v3('BTER/DOGEBTC', 'DOGE', 'BTC')
    load_quandl_v3('BTER/LTCBTC', 'LTC', 'BTC')
    load_quandl_v3('BTER/DASHBTC', 'DASH', 'BTC')

def load_quandl_v3(tag, crypto, fiat):
    url = "https://www.quandl.com/api/v3/datasets/%s.json?api_key=%s" % (
        tag, settings.QUANDL_APIKEY
    )
    source_name = tag.split("/")[0]
    response = requests.get(url).json()

    for line in response['dataset']['data']:
        tick_date = arrow.get(line[0]).datetime
        price = line[1]
        if price:
            price = float(price)

        p = PriceTick.record_price(
            price=price, crypto=crypto,
            fiat=fiat, source_name=source_name,
            at_time=tick_date,
            interval=datetime.timedelta(hours=1)
        )

        if p:
            print("made:", p)
        else:
            print("skipping", tick_date)

def get_ticks(verbose=False):
    """
    Run this function every 60 or so minutes so to keep the PriceTicks table
    fresh.
    """
    all_ticks = []
    for fiat in settings.WALLET_SUPPORTED_FIATS:
        all_ticks.append(PriceTick.get_current_price('btc', fiat, verbose=verbose))

    for crypto in [x['code'] for x in get_wallet_currencies()]:
        if crypto == 'btc':
            continue
        all_ticks.append(PriceTick.get_current_price(crypto, 'btc', verbose=verbose))

    return all_ticks
