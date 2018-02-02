import json
import arrow
import datetime

from django.utils import timezone
from django.db import models
from django.conf import settings
from .utils import datetime_to_iso
from moneywagon import get_single_transaction, get_block
from moneywagon.supply_estimator import SupplyEstimator
from pricetick.models import PriceTick

class CachedTransaction(models.Model):
    txid = models.CharField(max_length=72, primary_key=True)
    content = models.TextField()
    crypto = models.CharField(max_length=8, default='btc')

    date_fetched = models.DateTimeField(default=timezone.now)
    service_used = models.TextField(default="")

    def __unicode__(self):
        txid = "?"
        if self.content == "Pending":
            return "Pending"

        txid = json.loads(self.content)['txid']
        return "%s:%s" % (self.crypto.upper(), txid)

    @classmethod
    def fetch_full_tx(cls, crypto, txid, fiat=None):
        freshly_fetched = False
        try:
            tx_obj = cls.objects.get(crypto=crypto, txid=txid)
            if tx_obj.content == "Pending":
                return None
            if tx_obj.content == "Failed":
                raise cls.DoesNotExist()

            tx = json.loads(tx_obj.content)

            if tx.get('confirmations', 0) == 0:
                raise cls.DoesNotExist()

        except cls.DoesNotExist:
            # not cached, fetch from API service.
            tx_obj, c = cls.objects.get_or_create(crypto=crypto, txid=txid)
            tx_obj.content = "Pending"
            tx_obj.save()
            try:
                services, tx = get_single_transaction(crypto, txid, random=True, report_services=True)
            except Exception as exc:
                tx_obj.content = "Failed"
                tx_obj.service_used = str(exc)
                tx_obj.save()

                raise

            freshly_fetched = True
            tx_obj.content = json.dumps(tx, default=datetime_to_iso)
            su = services[0]
            tx_obj.service_used = "(%s) %s" % (su.service_id, su.name)
            tx_obj.crypto = crypto
            tx_obj.save()

            # if existing_tx_data and existing_tx_data.get('counterparty', False):
            #     tx['inputs'] = []
            #     tx['outputs'] = []
            #
            #     if existing_tx_data['amount'] > 0:
            #         # send, add amount to outputs
            #         which = "outputs"
            #     else:
            #         # receive, add amount to inputs
            #         which = "inputs"
            #
            #     tx[which] = [{}]
            #     tx[which][0]['amount'] = existing_tx_data['amount'] / 1e8
            #     tx[which][0]['address'] = existing_tx_data['address']


        time = arrow.get(tx['time']).datetime

        if fiat:
            tx['historical_price'] = cls.get_historical_fiat(crypto, fiat, time)

        if not freshly_fetched:
            try:
                tx['confirmations'] = SupplyEstimator(crypto).estimate_confirmations(time.replace(tzinfo=None))
            except:
                pass

        tx['memos'] = Memo.get(txid=txid, crypto=crypto)
        return tx

    @classmethod
    def get_historical_fiat(cls, crypto, fiat, time):
        try:
            return PriceTick.nearest(crypto, fiat, time)
        except PriceTick.DoesNotExist:
            return None


class Memo(models.Model):
    crypto = models.CharField(max_length=8, default='btc')
    encrypted_text = models.TextField(blank=False)
    txid = models.CharField(max_length=72, db_index=True)
    pubkey = models.TextField()
    signature = models.TextField(blank=True)
    created = models.DateTimeField(default=timezone.now)

    @classmethod
    def get(cls, crypto, txid):
        memos = cls.objects.filter(txid=txid, crypto=crypto).exclude(encrypted_text="Please Delete")
        return [x.encrypted_text for x in memos]

    def as_dict(self):
        return {
            'encrypted_text': self.encrypted_text,
            'txid': self.txid,
            'signature': self.signature,
            'pubkey': self.pubkey,
            'currency': self.crypto
        }

class PullHistory(models.Model):
    """
    Records when the last time a memo server has been pulled
    """
    last_pulled = models.DateTimeField(default=timezone.now)
    pull_url = models.TextField()

    def __unicode__(self):
        ago = (timezone.now() - self.last_pulled)
        return "%s (%s Ago)" % (self.pull_url, ago)

class PushHistory(models.Model):
    last_pushed = models.DateTimeField(default=timezone.now)


class IPTracker(models.Model):
    ip = models.CharField(max_length=64)
    last_unbanned = models.DateTimeField(default=timezone.now)
    hits = models.IntegerField(default=0)

    class Meta:
        get_latest_by = 'last_unbanned'

    @classmethod
    def allow(cls, ip):
        interval = datetime.timedelta(**settings.IP_FILTER_INTERVAL)
        if not cls.objects.filter(ip=ip).exists():
            cls.objects.create(ip=ip, hits=1)
            return True
        else:
            last = cls.objects.filter(ip=ip).latest()
            if last.hits > settings.IP_FILTER_HITS:
                interval_ago = timezone.now() - interval
                if last.last_unbanned < interval_ago:
                    cls.objects.create(ip=ip, hits=1)
                    return True
                return False
            else:
                last.hits += 1
                last.save()
                return True
