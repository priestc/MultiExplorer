import calendar
import datetime
import csv
import os
import StringIO

import arrow
import requests
import pytz

from django.db import models
from django.conf import settings
from django.utils import timezone

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
    def nearest(cls, date):
        """
        Find the tick nearest the passed in date.
        """
        return cls.objects.filter(date__lt=date).latest()

    @classmethod
    def get_current_price(cls, crypto, fiat, verbose=False):
        price = cls.get_non_stale_price(crypto, fiat)
        if price:
            return price
        sources, price = get_current_price(crypto, fiat, report_services=True, verbose=verbose)
        if not sources[0]:
            import debug
        tick = cls.record_price(price, crypto, fiat, sources[0].name)
        return tick

    @classmethod
    def record_price(cls, price, crypto, fiat, source_name):
        """
        If you already have the price data and want to record that, use this method.
        WIll only record if the current price is within PRICE_INTERVAL_SECONDS.
        """
        if cls.needs_update(crypto, fiat):
            obj = cls.objects.create(
                date=timezone.now(),
                price=price,
                base_fiat=fiat.upper(),
                currency=crypto.upper(),
                exchange=source_name
            )
            return obj
        return False

    @classmethod
    def get_non_stale_price(cls, crypto, fiat):
        try:
            price = cls.objects.filter(
                currency=crypto.upper(), base_fiat=fiat.upper()).latest()
        except cls.DoesNotExist:
            return None

        if price.is_stale():
            return None

        return price


    @classmethod
    def needs_update(cls, crypto, fiat):
        price = cls.get_non_stale_price(crypto, fiat)
        return price is None

    def is_stale(self):
        interval_ago = timezone.now() - datetime.timedelta(
            seconds=settings.PRICE_INTERVAL_SECONDS
        )
        return self.date < interval_ago

    class Meta:
        get_latest_by = 'date'


def load_btc():
    # $ cd ~
    # $ wget http://api.bitcoincharts.com/v1/csv/bitstampUSD.csv.gz | unp
    from os.path import expanduser
    home = os.path.expanduser("~")
    f = open(os.path.join(home, "bitstampUSD.csv"))
    for i, line in enumerate(f):
        timestamp, price, volume = line.split(",")
        tick_date = datetime.datetime.fromtimestamp(int(timestamp)).replace(tzinfo=pytz.UTC)

        if i % 300 == 0:
            p = PriceTick.objects.create(
                currency='BTC',
                exchange='bitstampUSD',
                base_fiat='USD',
                date=tick_date,
                price=price,
            )

            print p

def load_ltc():
    # https://www.quandl.com/BTCE/BTCLTC-BTC-LTC-Exchange-Rate
    url = "http://www.quandl.com/api/v1/datasets/TAMMER1/LTCUSD.csv"
    response = requests.get(url)
    reader = csv.DictReader(StringIO.StringIO(response.content))
    for line in reader:
        tick_date = arrow.get(line['Date']).datetime
        p = PriceTick.objects.create(
            currency='LTC',
            exchange='btc-e',
            base_fiat='BTC',
            date=tick_date,
            price=line['Close'],
        )
        print p


def load_from_CRYPTOCHART_at_quandl():
    """
    Using the quandl.com API, get the historical price (by day).
    All data comes from the CRYPTOCHART source, which claims to be from
    multiple exchange sources for price.
    """
    sources = [
        ['MYR', 'CRYPTOCHART/MYR', ],
        ['DOGE', 'CRYPTOCHART/DOGE'],
        ['PPC', 'CRYPTOCHART/PPC'],
        ['LTC', 'BTCE/BTCLTC'],
        ['VTC', 'CRYPTOCHART/VTC'],
        ['NXT', 'CRYPTOCHART/NXT'],
        ['FTC', 'CRYPTOCHART/FTC'],
    ]

    for currency, source in sources:
        url = "https://www.quandl.com/api/v1/datasets/%s.json" % source
        response = requests.get(url).json()
        for line in response['data']:
            tick_date = arrow.get(line[0]).datetime
            price = line[1]
            if price:
                price = float(price)

            p = PriceTick.objects.create(
                currency=currency,
                exchange=source.lower(),
                base_fiat='BTC',
                date=tick_date,
                price=price,
            )
            print p

def load_all():
    load_btc()
    load_from_CRYPTOCHART_at_quandl()

def get_ticks(verbose=False):
    """
    Run this function every 60 or so minutes so to keep the PriceTicks table
    fresh.
    """
    all_ticks = []
    for fiat in ['usd', 'cny', 'rur', 'eur']:
        all_ticks.append(PriceTick.get_current_price('btc', fiat, verbose=verbose))

    for crypto in ['ltc', 'doge', 'nxt', 'ppc', 'vtc', 'ftc', 'myr']:
        all_ticks.append(PriceTick.get_current_price(crypto, 'btc', verbose=verbose))

    return all_ticks
