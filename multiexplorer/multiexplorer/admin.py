import json
from django.contrib import admin
from .models import CachedTransaction
from django.utils.safestring import mark_safe


class CachedTransactionAdmin(admin.ModelAdmin):
    list_display = ("txid", 'crypto', "content_length")
    readonly_fields = ('pretty_print', )

    def pretty_print(self, obj):
        return mark_safe("<br><pre>%s</pre" % json.dumps(
            json.loads(obj.content), indent=4
        ))

    def content_length(self, obj):
        return len(obj.content)

admin.site.register(CachedTransaction, CachedTransactionAdmin)
