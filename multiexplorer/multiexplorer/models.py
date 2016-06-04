import json
from django.db import models
from .utils import datetime_to_iso
from moneywagon import get_single_transaction, get_block

class CachedTransaction(models.Model):
    txid = models.CharField(max_length=72, primary_key=True)
    content = models.TextField()
    crypto = models.CharField(max_length=8, default='btc')

    @classmethod
    def fetch_full_tx(cls, crypto, txid, confirmations=None):
        try:
            tx = cls.objects.get(txid=txid)
            if not tx.content:
                return None
            transaction = json.loads(tx.content)
            if confirmations:
                # update cached entry with updated confirmations if its available
                transaction['confirmations'] = confirmations
                tx.content = json.dumps(transaction)
                tx.save()
            return transaction
        except cls.DoesNotExist:
            cache = cls.objects.create(txid=txid, content="")
            tx = get_single_transaction(crypto, txid, random=True)
            cache.content = json.dumps(tx, default=datetime_to_iso)
            cache.crypto = crypto
            cache.save()
            return tx

    def update_confirmations(self):
        current_block = get_block(self.crypto, latest=True)
