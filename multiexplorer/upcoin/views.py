# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json
import dateutil.parser

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.db.models import Q

from .models import LedgerEntry, Peer
from bitcoin import ecdsa_sign, ecdsa_verify, ecdsa_recover, pubtoaddr
from .tx_util import InvalidTransaction, validate_transaction

def send_tx(request):
    return render(request, "send_tx.html")

def accept_tx(request):
    try:
        tx = json.loads(request.POST['tx'])
    except:
        return HttpResponseBadRequest("Invalid transaction JSON")

    ts = dateutil.parser.parse(datetime.tx['timestamp'])
    print ts - datetime.datetime.now()

    if ts - datetime.datetime.now() < datetime.timedelta(seconds=5):
        pass

    for i, input in enumerate(tx['inputs']):
        address, amount, sig = input

        try:
            entry = LedgerEntry.objects.get(address=address)
        except LegderEntry.DoesNotExist:
            return HttpResponseBadRequest(
                "Address %s does not exist" % address
            )
        if entry.amount <= amount:
            return HttpResponseBadRequest(
                "Address %s does not have enough balance" % address
            )

    try:
        validate_transaction(tx)
    except InvalidTransaction as exc:
        return HttpResponseBadRequest("Transaction Invalid: %s" % str(exc))

    for input in inputs:
        entry = LegderEntry.objects.get(address=input['address'])

    for output in outputs:
        entry = LedgerEntry.objects.get_or_create()

    return HttpResponse("OK")

def pass_on_to_peers(obj):
    peers = Peer.objects.all()

def get_peers(request):
    pass

def add_peer(request):
    try:
        reg = json.loads(request.POST['registration'])
    except Exception as exc:
        return HttpResponseBadRequest("Invalid transaction JSON: %s" % str(exc))

    for item in ['signature', 'timestamp', 'domain', 'payout_address']:
        if item not in reg:
            return HttpResponseBadRequest(
                "%s missing" % item.replace("_", " ").title()
            )

    ts = dateutil.parser.parse(reg['timestamp'])
    if ts - datetime.datetime.now() > datetime.timedelta(seconds=10):
        return HttpResponseBadRequest("Timestamp too old")

    try:
        p = Peer.objects.get(
            Q(domain=reg['domain']) | Q(payout_address=reg['payout_address'])
        )
        p.domain = reg['domain']
        p.payout_address = reg['payout_address']
        p.save()
    except Peer.DoesNotExist:
        Peer.objects.create(
            domain=reg['domain'],
            payout_address=reg['payout_address'],
            first_registered=ts
        )

    pass_on_to_peers(reg)

    return HttpResponse("OK")

def ping(request):
    pass

def network_summary(request):
    peers = Peer.objects.all()
    return render(request, "upcoin_summary.html", locals())
