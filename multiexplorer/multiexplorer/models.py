import json

from django.utils import timezone
from django.db import models
from .utils import datetime_to_iso
from moneywagon import get_single_transaction, get_block

class CachedTransaction(models.Model):
    txid = models.CharField(max_length=72, primary_key=True)
    content = models.TextField()
    crypto = models.CharField(max_length=8, default='btc')

    def __unicode__(self):
        return "%s:%s" % (self.crypto.upper(), json.loads(self.content)['txid'])

    @classmethod
    def fetch_full_tx(cls, crypto, txid, existing_tx_data=None):
        try:
            tx_obj = cls.objects.get(txid=txid)
            if not tx_obj.content:
                return None
            tx = json.loads(tx_obj.content)

            if existing_tx_data and existing_tx_data.get('confirmations', None):
                # update cached entry with updated confirmations if its available
                tx['confirmations'] = existing_tx_data['confirmations']
                tx_obj.content = json.dumps(tx)
                tx_obj.save()

        except cls.DoesNotExist:
            tx_obj = cls.objects.create(txid=txid, content="")
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

            tx_obj.content = json.dumps(tx, default=datetime_to_iso)
            tx_obj.crypto = crypto
            tx_obj.save()

        tx['memos'] = [x.encrypted_text for x in Memo.objects.filter(txid=txid, crypto=crypto)]
        return tx

    def update_confirmations(self):
        current_block = get_block(self.crypto, latest=True)

class Memo(models.Model):
    crypto = models.CharField(max_length=8, default='btc')
    encrypted_text = models.TextField(blank=False)
    txid = models.CharField(max_length=72, db_index=True)
    pubkey = models.TextField()
    created = models.DateTimeField(default=timezone.now)

class PullHistory(models.Model):
    """
    Records when the last time a memo server has been pulled
    """
    last_pulled = models.DateTimeField(default=timezone.now)
    pull_url = models.TextField()

    def __unicode__(self):
        ago = (timezone.now() - self.last_pulled)
        return "%s (%s Ago)" % (self.pull_url, ago)
