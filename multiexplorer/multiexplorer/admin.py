import json
from django.contrib import admin
from .models import CachedTransaction, Memo
from django.utils.safestring import mark_safe

class CachedTransactionAdmin(admin.ModelAdmin):
    list_display = ("txid", 'crypto', "content_length")
    readonly_fields = ('pretty_print', )
    search_fields = ('txid', )

    def pretty_print(self, obj):
        return mark_safe("<br><pre>%s</pre" % json.dumps(
            json.loads(obj.content), indent=4
        ))

    def content_length(self, obj):
        return len(obj.content)

class MemoAdmin(admin.ModelAdmin):
    list_display = ("txid", "content_length", 'crypto', 'created')
    ordering = ('-created',)

    def content_length(self, obj):
        return len(obj.encrypted_text)

admin.site.register(CachedTransaction, CachedTransactionAdmin)
admin.site.register(Memo, MemoAdmin)
