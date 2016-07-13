# -*- coding: utf-8 -*-

import datetime
import json
from django.db import models
from moneywagon import get_single_transaction

# Create your models here.

AUTO_LOGOUT_CHOICES = (
    (5, "5 minutes of inactivity"),
    (30, "30 minutes of inactivity"),
    (0, "Never"),
)


class WalletMasterKeys(models.Model):
    """
    Stores the BIP32 HD master seed for the user's wallet.
    The seed is stored encrypted with the user's password.
    """
    user = models.ForeignKey('auth.User')
    encrypted_mnemonic = models.CharField(max_length=172)

    auto_logout = models.IntegerField(choices=AUTO_LOGOUT_CHOICES, default=0)
    display_fiat = models.CharField(max_length=5, default='usd')
    show_wallet_list = models.TextField(
        default='btc,ltc,doge,dash')  # comma seperated

    def __unicode__(self):
        return "Master key of user: %s (UID: %d)" % (self.user.username, self.user.id)

    def __str__(self):
        return self.__unicode__()

    def get_show_wallet_list(self):
        return self.show_wallet_list.split(",")

    def get_settings(self):
        if self.display_fiat in ['cad', 'usd']:
            symbol = '$'
        elif self.display_fiat == 'eur':
            symbol = '€'
        elif self.display_fiat == 'gbp':
            symbol = '£'
        elif self.display_fiat in ['jpy', 'cny']:
            symbol = '¥'
        else:
            symbol = ''

        return {
            'show_wallet_list': self.get_show_wallet_list(),
            'display_fiat_unit': self.display_fiat,
            'display_fiat_symbol': symbol,
            'auto_logout': self.auto_logout
        }


class FailedLogin(models.Model):
    username = models.CharField(max_length=64, db_index=True)
    time = models.DateTimeField(default=datetime.datetime.now)

    class Meta:
        get_latest_by = 'time'
