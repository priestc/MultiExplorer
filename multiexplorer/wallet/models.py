from django.db import models

# Create your models here.

class WalletMasterKeys(models.Model):
    """
    Stores the BIP32 HD master seed for the user's wallet.
    The seed is stored encrypted with the user's password.
    """
    user = models.ForeignKey('auth.User')
    encrypted_mnemonic = models.CharField(max_length=172)

    def __unicode__(self):
        return self.user.username
