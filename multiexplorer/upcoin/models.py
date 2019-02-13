# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models

class LedgerEntry(models.Model):
    address = models.TextField(max_length=40)
    amount = models.IntegerField(default=0)
    last_updated = models.DateTimeField()

class Peer(models.Model):
    domain = models.TextField()
    reputation = models.FloatField(default=0)
