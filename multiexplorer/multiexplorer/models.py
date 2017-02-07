import json
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
            tx = cls.objects.get(txid=txid)
            if not tx.content:
                return None
            transaction = json.loads(tx.content)

            if existing_tx_data and existing_tx_data.get('confirmations', None):
                # update cached entry with updated confirmations if its available
                transaction['confirmations'] = existing_tx_data['confirmations']
                tx.content = json.dumps(transaction)
                tx.save()
            return transaction
        except cls.DoesNotExist:
            cache = cls.objects.create(txid=txid, content="")
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

            cache.content = json.dumps(tx, default=datetime_to_iso)
            cache.crypto = crypto
            cache.save()
            return tx

    def update_confirmations(self):
        current_block = get_block(self.crypto, latest=True)

class Memo(models.Model):
    encrypted_text = models.TextField(blank=False)
    txid = models.ForeignKey(CachedTransaction)
    pubkey = models.TextField()
