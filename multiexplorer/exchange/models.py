import datetime
import json
import os

from django.db import models
from django.conf import settings
from django.utils import timezone
from bitcoin import bip32_ckd, bip32_master_key, bip32_extract_key, privtoaddr
from moneywagon.tx import Transaction
from moneywagon import get_unspent_outputs, get_current_price
from multiexplorer.utils import get_wallet_currencies
from multiexplorer.models import CachedTransaction

SUPPORTED_CURRENCIES = [(x['bip44'], "%(code)s - %(name)s" % x) for x in get_wallet_currencies()]

class ExchangeMasterKey(models.Model):
    created = models.DateTimeField(default=timezone.now)
    xpriv = models.CharField(max_length=120, blank=True)
    from_passphrase = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    utxos = models.TextField(blank=True)

    class Meta:
        get_latest_by = 'created'

    def save(self, *args, **kwargs):
        if not self.xpriv:
            seed_words = self.from_passphrase and self.from_passphrase.encode('ascii')
            self.xpriv = bip32_master_key(seed=seed_words or os.urandom(100))
            self.from_passphrase = ''

        return super(ExchangeMasterKey, self).save(*args, **kwargs)

    def cached_balance(self, currency):
        if not self.utxos:
            return 0

        try:
            utxos = json.loads(self.utxos)[currency]
        except KeyError:
            return 0

        balance = 0
        for utxo in utxos:
            balance += utxo['amount']

        return balance / 1e8 # convert satoshis to currency units

    def get_unused_addresses(self, currency, length=5):
        i = 0
        addresses = []
        while len(addresses) < length:
            address, priv_key = currency.derive_deposit_address(i, self)
            is_used1 = ManualDeposit.objects.filter(address=address, currency=currency).exists()
            is_used2 = ExchangeAddress.objects.filter(deposit_address=address, deposit_currency__code=currency).exists()

            if not is_used1 and not is_used2:
                addresses.append(address)

            i += 1
        return addresses

FIAT_CHOICES = [(x, x.upper()) for x in settings.WALLET_SUPPORTED_FIATS]

class ExchangeCurrency(models.Model):
    currency = models.IntegerField(choices=SUPPORTED_CURRENCIES, primary_key=True)
    fee_percentage = models.FloatField(default=0.01)
    code = models.CharField(max_length=5, null=True, blank=True)
    max_fiat_deposit = models.FloatField(default=10)
    max_fiat_currency = models.CharField(max_length=4, choices=FIAT_CHOICES, default='usd')

    @classmethod
    def get_active(cls, code):
        obj = cls.objects.get(code=code)
        if obj.balance == 0:
            raise cls.DoesNotExist("%s is temporairly out of order" % code.upper())
        return obj

    def __unicode__(self):
        return "%s" % self.code

    def save(self, *args, **kwargs):
        if not self.code:
            for currency in get_wallet_currencies():
                if currency['bip44'] == self.currency:
                    self.code = currency['code']

        return super(ExchangeCurrency, self).save(*args, **kwargs)

    def name(self):
        for currency in get_wallet_currencies():
            if currency['bip44'] == self.currency:
                return currency['name']

    def logo(self):
        for currency in get_wallet_currencies():
            if currency['bip44'] == self.currency:
                return currency['logo']

    def get_address_byte(self):
        for currency in get_wallet_currencies():
            if currency['bip44'] == self.currency:
                return currency['address_byte']

    def balance(self):
        balance = 0
        for master_key in ExchangeMasterKey.objects.order_by('created'):
            balance += master_key.cached_balance(self.code)

        return balance

    def get_bip44_master(self, master_key):
        return bip32_ckd(bip32_ckd(master_key.xpriv, 44), self.currency)

    def _derive_address(self, change_or_deposit, index, master_key):
        xpriv = bip32_ckd(bip32_ckd(self.get_bip44_master(master_key), change_or_deposit), index)
        priv = bip32_extract_key(xpriv)
        address = privtoaddr(priv, self.get_address_byte())
        return address, priv

    def derive_exchange_address(self, index, master_key):
        return self._derive_address(1, index, master_key)

    def derive_deposit_address(self, index, master_key):
        return self._derive_address(0, index, master_key)

    def fast_reload(self, master_key):
        addresses = []
        for i in range(self.deposit_skip, self.deposit_skip + 10):
            addresses.append(self.derive_deposit_address(i, master_key))

        for i in range(self.change_skip, self.change_skip + 10):
            addresses.append(self.derive_change_address(i, master_key))

        utxos = get_unspent_outputs(crypto=self.code, addresses=addresses)

        self.save()

    def add_utxos(self, utxos, master_key):
        utxos = json.loads(master_key.utxos)
        utxos[self.currency].extend(utxo)
        # sort so the highest value utxo is first
        utxos[self.currency].sort(key=lambda x: x['amount'], reverse=True)
        master_key.utxos = json.dumps(utxos)
        master_key.save()

    def pop_utxos(self, amount):
        utxos = json.loads(self.utxos)
        popped = []
        left = []
        total_added = 0
        for utxo in utxos:
            if total_added >= amount:
                left.append(utxo)
                continue

            popped.append(utxos)
            total_added += utxo['amount']

        self.utxos = json.dumps(left)
        self.save()

        return popped


class ManualDeposit(models.Model):
    currency = models.ForeignKey(ExchangeCurrency, on_delete=models.CASCADE)
    address = models.CharField(max_length=50)
    master_key = models.ForeignKey(ExchangeMasterKey, on_delete=models.CASCADE)


class ExchangeAddress(models.Model):
    created = models.DateTimeField(default=timezone.now)
    last_kick = models.DateTimeField(default=None, null=True)

    # the user sends funds to this address (address generated by us)
    deposit_currency = models.ForeignKey(ExchangeCurrency, related_name="incoming_exchanges", on_delete=models.CASCADE)
    deposit_address = models.CharField(max_length=128)

    exchange_rate = models.FloatField(null=True)

    # we send the exchanged funds to this address (address supplied by the user)
    withdraw_currency = models.ForeignKey(ExchangeCurrency, related_name="outgoing_exchanges", on_delete=models.CASCADE)
    withdraw_address = models.CharField(max_length=128, blank=True)

    def __unicode__(self):
        return "%s -> %s" % (self.deposit_currency, self.withdraw_address)

    def seconds_to_needing_kick(self):
        last_kick = self.last_kick
        since_last_kick = (timezone.now() - last_kick).total_seconds()
        return (settings.EXCHANGE_KICK_INTERVAL_MINUTES * 60) - since_last_kick

    def kick(self):
        if self.last_kick: # already been kicked
            if self.seconds_to_needing_kick() < 0:
                return # kick not needed

        if not self.withdraw_address:
            master_key = ExchangeMasterKey.objects.latest()
            self.withdraw_address = master_key.get_unused_addresses(self.withdraw_currency, 1)[0]

        if not self.deposit_address:
            master_key = ExchangeMasterKey.objects.latest()
            self.deposit_address = master_key.get_unused_addresses(self.deposit_currency, 1)[0]

        self.last_kick = timezone.now()
        self.exchange_rate = self.calculate_exchange_rate()
        self.save()

    def calculate_exchange_rate(self):
        deposit_price = get_current_price(crypto=self.deposit_currency.code, fiat='usd')
        withdraw_price = get_current_price(crypto=self.withdraw_currency.code, fiat='usd')
        raw_rate = deposit_price / withdraw_price
        rate_with_fee = raw_rate * (1 + (settings.EXCHANGE_FEE_PERCENTAGE / 100.0))
        return rate_with_fee

class ExchangeWithdraw(models.Model):
    exchange = models.ForeignKey(ExchangeAddress, on_delete=models.CASCADE)
    deposit_txid = models.TextField()
    withdraw_inputs = models.TextField()
    withdraw_confirmed = models.BooleanField(default=False)

    def withdraw_amount(self):
        tx = CachedTransaction.objects.fetch_full_tx(
            crypto=self.deposit_currency.code,
            txid=self.deposit_txid
        )
        return tx.total_input_amount * self.exchange.exchange_rate

    def make_payment(self):
        tx = Transaction(crypto=self.withdraw_currency.code)
        tx.add_inputs(self.exchange.withdraw_currency.pop_utxos(self.withdraw_amount))
        tx.add_output(self.withdraw_amount, to_address)
        return tx.push_tx()
