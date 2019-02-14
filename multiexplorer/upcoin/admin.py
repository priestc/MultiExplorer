# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from .models import LedgerEntry, Peer

class PeerAdmin(admin.ModelAdmin):
    pass

class LedgerAdmin(admin.ModelAdmin):
    pass

admin.site.register(Peer, PeerAdmin)
admin.site.register(LedgerEntry, LedgerAdmin)
