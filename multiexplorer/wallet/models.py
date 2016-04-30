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
    show_wallet_list = models.TextField(default='btc,ltc,doge') # comma seperated

    def __unicode__(self):
        return self.user.username

    def get_show_wallet_list(self):
        return self.show_wallet_list.split(",")

    def get_settings(self):
        return {
            'show_wallet_list': self.get_show_wallet_list(),
            'display_fiat': self.display_fiat,
            'auto_logout': self.auto_logout
        }
