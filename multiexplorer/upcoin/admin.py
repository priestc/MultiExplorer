# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from .models import LedgerEntry, Peer

class PeerAdmin(admin.ModelAdmin):
    list_display = ('domain', 'reputation', 'payout_address', 'first_registered')
    ordering = ('-reputation', 'first_registered')

class LedgerAdmin(admin.ModelAdmin):
    list_display = ('address', 'amount', 'last_updated')

admin.site.register(Peer, PeerAdmin)
admin.site.register(LedgerEntry, LedgerAdmin)
