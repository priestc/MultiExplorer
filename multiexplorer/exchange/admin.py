import json
from django.contrib import admin
from .models import ExchangeCurrency, ExchangeMasterKey

class ExchangeMasterKeyAdmin(admin.ModelAdmin):
    list_display = ("created", 'notes', 'balances')
    readonly_fields = ('xpriv', )

    def balances(self, master_key):
        balances = ""
        for currency in ExchangeCurrency.objects.all():
            balances += "%s - %.8f<br>" % (
                currency.code.upper(), master_key.cached_balance(currency.code)
            )
            #raise Exception()
        return balances
    balances.allow_tags = True

class ExchangeCurrencyAdmin(admin.ModelAdmin):
    list_display = ("get_currency_display", 'balance', 'deposit')
    readonly_fields = ('balance', 'deposit_qrcodes')

    class Media:
        js = (
            'admin-jquery-fixer.js',
            'jquery.qrcode.min.js',
            'make_admin_qr.js',
        )

    def deposit(self, currency):
        master_key = ExchangeMasterKey.objects.latest()
        addresses = master_key.get_unused_deposit_addresses(currency, 1)
        return "<span class='qr' data-size='small' data-address='{0}'></span><br>{0}".format(addresses[0])
    deposit.allow_tags = True

    def deposit_qrcodes(self, currency):
        master_key = ExchangeMasterKey.objects.latest()
        addresses = master_key.get_unused_deposit_addresses(currency, 5)
        return '<br>'.join(
            "<span class='qr' data-size='medium' data-address='{0}'></span><br>{0}<br><br>".format(x) for x in addresses
        )
    deposit_qrcodes.allow_tags = True


admin.site.register(ExchangeCurrency, ExchangeCurrencyAdmin)
admin.site.register(ExchangeMasterKey, ExchangeMasterKeyAdmin)
