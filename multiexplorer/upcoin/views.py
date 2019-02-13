# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest

from .models import LegerEntry, Peer
from bitcoin import ecdsa_sign, ecdsa_verify, ecdsa_recover, pubtoaddr

def accept_tx(request):
    inputs = request.POST['inputs']
    outputs = request.POST['outputs']

    for i, input in enumerate(inputs.split(":")):
        address, amount, sig = input.split(",")

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

        message = "%s%s%s" % (address, amount, outputs)
        pubkey = ecdsa_recover(message, sig)
        if not ecdsa_verify(message, sig, pubkey) and pubtoaddr(pubkey) == address:
            return HttpResponseBadRequest(
                "Input %s has invalid signature" % i
            )

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
