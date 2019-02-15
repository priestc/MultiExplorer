# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import itertools
import hashlib

from django.db import models

class LedgerEntry(models.Model):
    address = models.TextField(max_length=40)
    amount = models.IntegerField(default=0)
    last_updated = models.DateTimeField()

    @classmethod
    def ledger_hash(cls, epoch):
        epoch_end = genesis_date + datetime.timedelta(minutes=10 * epoch)
        LedgerEntry.objects.filter(last_updated__lte=epoch_end)

class Peer(models.Model):
    domain = models.TextField()
    reputation = models.FloatField(default=0)
    first_registered = models.DateTimeField()
    payout_address = models.TextField(max_length=40)

    def __unicode__(self):
        return self.domain

    @classmethod
    def shuffle(cls, hash, n=0):
        peers = list(cls.objects.all().order_by('reputation'))
        sorter = lambda x: hashlib.sha256(x.domain + hash + n).hexdigest()
        return sorted(peers, key=sorter)
