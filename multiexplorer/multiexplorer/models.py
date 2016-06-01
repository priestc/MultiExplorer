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
            if not tx.content:
                return None
            return json.loads(tx.content)
        except cls.DoesNotExist:
            cache = cls.objects.create(txid=txid, content="")
            tx = get_single_transaction(crypto, txid, random=True)
            cache.content = json.dumps(tx, default=datetime_to_iso)
            cache.save()
            return tx
