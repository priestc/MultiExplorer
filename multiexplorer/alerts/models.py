# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import datetime
import math
import json

from django.db import models
from moneywagon import crypto_data

class FraudAlert(models.Model):
    fraud_services = models.TextField()
    network_results = models.TextField()
    offending_type = models.CharField(max_length=32)
    offending_value = models.TextField()
    offending_currency = models.CharField(max_length=6)
    date_created = models.DateTimeField(default=datetime.datetime.now)

    def __unicode__(self):
        return "%s %s %s" % (self.fraud_services, self.offending_currency, self.offending_type)

    @classmethod
    def new_alert(cls, currency, network_results, txid=None, address=None):
        """
        >>> from moneywagon.services import BadService, GDAX
        >>> FraudAlert.new_alert('btc', {BadService(): 0, GDAX(): 45}, address='1F1xcRt8H8Wa623KqmkEontwAAVqDSAWCV')
        """
        print("== passed in", address, txid)
        if address:
            field = 'address_balance'
            kwargs = dict(to_call='get_balance', call_arg=address, type='balance')
        elif txid:
            field = 'get_single_transaction'
            kwargs = dict(to_call='get_single_transaction', call_arg=txid, type='txid')

        all_services = crypto_data[currency.lower()]['services'][field]
        return cls._make_alert(currency, network_results, all_services, **kwargs)

    @classmethod
    def _make_alert(cls, currency, network_results, all_services, to_call, call_arg, type):
        already_service_names = [x.name for x in network_results.keys()]
        for Service in all_services:
            if Service.name not in already_service_names:
                s = Service(verbose=True)
                val = getattr(s, to_call)(currency, call_arg)
                network_results[s] = val

        fraud_services = cls._find_fraud_services(network_results)

        alert = cls.objects.create(
            fraud_services=", ".join(x.name for x in fraud_services),
            offending_value=call_arg,
            offending_currency=currency,
            offending_type=type,
            network_results=json.dumps({
                "(%s) %s" % (s.service_id, s.name): v for s, v in network_results.items()
            })
        )
        return alert

    @classmethod
    def _find_fraud_services(cls, network_results):
        """
        >>> FraudAlert._find_fraud_services({'a': 5, 'b': 5, 'c': 2}) # one disagrees
        ['c']
        >>> FraudAlert._find_fraud_services({'a': 5, 'b': 5, 'c': 5}) # all agree
        []
        >>> FraudAlert._find_fraud_services({'a': 5, 'b': 5, 'c': 2, 'd': 2, 'e': 2, 'f': 7})
        ['a', 'b', 'f']
        >>> FraudAlert._find_fraud_services({'a': 5, 'b': 4, 'c': 3}) # none agree
        ['a', 'b', 'c']
        >>> FraudAlert._find_fraud_services({'a': 5, 'b': 5, 'c': 3, 'd': 3}) # evenly partitioned
        ['a', 'b', 'c', 'd']
        """
        fraud_services = []
        consensus_min = math.ceil((len(network_results)+1) / 2.0) # 51%
        for service_to_check, value_to_check in network_results.items():
            match_count = 0
            for service, result in network_results.items():
                if result == value_to_check:
                    match_count += 1
            if match_count < consensus_min:
                fraud_services.append(service_to_check)

        return fraud_services
