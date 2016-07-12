from django.contrib import admin
from .models import WalletMasterKeys
# Register your models here.


class MasterAdmin(admin.ModelAdmin):
    readonly_fields = ('encrypted_mnemonic', )

admin.site.register(WalletMasterKeys, MasterAdmin)
