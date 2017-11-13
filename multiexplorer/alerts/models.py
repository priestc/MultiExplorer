# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import datetime
import math

from django.db import models
from moneywagon import crypto_data

class FraudAlert(models.Model):
    fraud_services = models.TextField()
    network_results = models.TextField()
    offending_type = models.IntegerField(choices=((0, "address"), (1, "txid")))
    offending_value = models.TextField()
    offending_currency = models.CharField(max_length=6)
    date_created = models.DateTimeField(default=datetime.datetime.now)

    def __unicode__(self):
        return "%s %s %s" % (self.fraud_services, self.offending_currency, self.offending_type)

    @classmethod
    def new_alert(cls, currency, already_called_services, results, txid=None, address=None):
        if address:
            field = 'address_balance'
            kwargs = dict(to_call='address_balance', call_arg=txid, type='balance')
        elif txid:
            field = 'get_single_transaction'
            kwargs = dict(to_call='get_single_transaction', call_arg=address, type='txid')

        all_services = crypto_data[currency.lower()]['services'][field]
        return cls._make_alert(currency, already_called_services, results, all_services, **kargs)

    @classmethod
    def _make_alert(cls, currency, already_called_services, results, all_services, to_call, call_arg, type):
        already_service_names = [x.name for x in already_called_services]
        for Service in all_services:
            if Service.name not in already_service_names:
                s = Service()
                results.append(getattr(s, to_call)(currency, call_arg))
                services.append(s)

        network_results = {
            service.name: result for service, result in zip(services, results)
        }

        fraud_services = cls._find_fraud_services(network_results)

        alert = cls.objects.create(
            fraud_services=", ".join(x.name for x in fraud_services),
            offending_value=call_arg,
            offending_currency=currency,
            offending_type=type,
            network_results=json.dumps(network_results)
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
