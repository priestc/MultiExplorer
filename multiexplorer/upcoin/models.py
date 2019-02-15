# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import itertools
import hashlib
import datetime

from django.db import models

genesis = datetime.datetime(2019, 2, 14, 10, 0)

def get_epoch_range(n):
    start =  genesis + datetime.timedelta(minutes=10 * n)
    return start, start + datetime.timedelta(minutes=10)

def get_epoch_number(time):
    delta = time - genesis
    return int("%d" % (delta.total_seconds() / 600))

class LedgerEntry(models.Model):
    address = models.TextField(max_length=40)
    amount = models.IntegerField(default=0)
    last_updated = models.DateTimeField()

    @classmethod
    def ledger_hash(cls, epoch):
        epoch_start, epoch_end = get_epoch_range(epoch)
        ledgers = LedgerEntry.objects.filter(
            last_updated__lte=epoch_end,
            last_updated__gte=epoch_start,
        ).order_by()
        return hashlib.sha256("".join([
            "%s%s" % (x.address, x.amount) for x in ledgers
        ]) + str(epoch)).hexdigest()


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

class EpochTransactions(models.Model):
    epoch_number = models.IntegerField()
    transactions = models.TextField()

    def adjustment_for_address(self, address):
        pass
