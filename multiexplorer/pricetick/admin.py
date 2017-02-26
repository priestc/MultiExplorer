from django.contrib import admin
from models import PriceTick

class PriceTickAdmin(admin.ModelAdmin):
    list_display = ['date', 'base_fiat', 'currency', 'exchange', 'price']

admin.site.register(PriceTick, PriceTickAdmin)
