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
        return balances
    balances.allow_tags = True

class ExchangeCurrencyAdmin(admin.ModelAdmin):
    list_display = ("get_currency_display", 'balance')
    readonly_fields = ('balance', 'deposit_qrcodes')

    def deposit_qrcodes(self, currency):
        master_key = ExchangeMasterKey.objects.latest()
        addresses = master_key.get_unused_deposit_addresses(currency, 5)
        return ', '.join(addresses)

admin.site.register(ExchangeCurrency, ExchangeCurrencyAdmin)
admin.site.register(ExchangeMasterKey, ExchangeMasterKeyAdmin)
