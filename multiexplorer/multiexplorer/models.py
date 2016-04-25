import json
from django.db import models
from .utils import datetime_to_iso
from moneywagon import get_single_transaction

class CachedTransaction(models.Model):
    txid = models.CharField(max_length=72, primary_key=True)
    content = models.TextField()

    @classmethod
    def fetch_full_tx(cls, crypto, txid):
        try:
            tx = cls.objects.get(txid=txid)
            return json.loads(tx.content)
        except cls.DoesNotExist:
            tx = get_single_transaction(crypto, txid, random=True)
            cls.objects.create(
                txid=txid,
                content=json.dumps(tx, default=datetime_to_iso),
            )
            return tx
