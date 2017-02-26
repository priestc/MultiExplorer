import json
import arrow
from django.utils import timezone
from django.db import models
from .utils import datetime_to_iso
from moneywagon import get_single_transaction, get_block
from pricetick.models import PriceTick

class CachedTransaction(models.Model):
    txid = models.CharField(max_length=72, primary_key=True)
    content = models.TextField()
    crypto = models.CharField(max_length=8, default='btc')

    def __unicode__(self):
        txid = "?"
        if self.content:
            txid = json.loads(self.content)['txid']
        return "%s:%s" % (self.crypto.upper(), txid)

    @classmethod
    def fetch_full_tx(cls, crypto, txid, existing_tx_data=None, fiat=None):
        try:
            tx_obj = cls.objects.get(txid=txid)
            if tx_obj.content == "Pending":
                return None
            tx = json.loads(tx_obj.content)

            if existing_tx_data and existing_tx_data.get('confirmations', None):
                # update cached entry with updated confirmations if its available
                tx['confirmations'] = existing_tx_data['confirmations']
                tx_obj.content = json.dumps(tx)
                tx_obj.save()

        except cls.DoesNotExist:
            # not cached, fetch from API service.
            tx_obj, c = cls.objects.get_or_create(txid=txid, content="Pending")
            tx = get_single_transaction(crypto, txid, random=True)

            if existing_tx_data and existing_tx_data.get('counterparty', False):
                tx['inputs'] = []
                tx['outputs'] = []

                if existing_tx_data['amount'] > 0:
                    # send, add amount to outputs
                    which = "outputs"
                else:
                    # receive, add amount to inputs
                    which = "inputs"

                tx[which] = [{}]
                tx[which][0]['amount'] = existing_tx_data['amount'] / 1e8
                tx[which][0]['address'] = existing_tx_data['address']

            if tx['confirmations'] > 0:
                tx_obj.content = json.dumps(tx, default=datetime_to_iso)
                tx_obj.crypto = crypto
                tx_obj.save()

        if fiat:
            try:
                price, source = PriceTick.nearest(crypto, fiat, arrow.get(tx['time']).datetime)
                d = {'fiat': fiat, 'price': price, 'source': source}
            except PriceTick.DoesNotExist:
                d = None

            tx['historical_fiat'] = d


        tx['memos'] = Memo.get(txid=txid, crypto=crypto)
        return tx

    def update_confirmations(self):
        current_block = get_block(self.crypto, latest=True)

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
