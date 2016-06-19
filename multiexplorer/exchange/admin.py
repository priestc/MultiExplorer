import json
from django.contrib import admin
from .models import ExchangeCurrency, ExchangeMasterKey

class ExchangeMasterKeyAdmin(admin.ModelAdmin):
    list_display = ("created", )

class ExchangeCurrencyAdmin(admin.ModelAdmin):
    list_display = ("get_currency_display", )

admin.site.register(ExchangeCurrency, ExchangeCurrencyAdmin)
admin.site.register(ExchangeMasterKey, ExchangeMasterKeyAdmin)
