# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json
import dateutil.parser

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest

from .models import LedgerEntry, Peer
from bitcoin import ecdsa_sign, ecdsa_verify, ecdsa_recover, pubtoaddr
from .tx_util import InvalidTransaction, validate_transaction


def accept_tx(request):
    try:
        tx = json.loads(request.POST['tx'])
    except:
        return HttpResponseBadRequest("Invalid transaction JSON")

    ts = dateutil.parser.parse(datetime.tx['timestamp'])

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

def get_peers(request):
    pass

def add_peer(request):
    pass

def ping(request):
    pass

def network_summary(request):
    nodes = Peer.objects.all()
    return render(request, "upcoin_summary.html", locals())
