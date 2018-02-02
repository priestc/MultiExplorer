import datetime
import json

from django.contrib import admin
from django.conf import settings
from django.utils import timezone

from .models import CachedTransaction, Memo, IPTracker
from django.utils.safestring import mark_safe

class CachedTransactionAdmin(admin.ModelAdmin):
    list_display = ("txid", 'crypto', "content_length", "date_fetched", "service_used")
    readonly_fields = ('pretty_print', )
    search_fields = ('txid', 'content')
    ordering = ("-date_fetched", )

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

class IPTrackerAdmin(admin.ModelAdmin):
    list_display = ('ip', 'colored_last_unbanned', 'hits')

    def colored_last_unbanned(self, obj):
        interval_ago = timezone.now() - datetime.timedelta(**settings.IP_FILTER_INTERVAL)
        if obj.last_unbanned > interval_ago:
            return "%s <span style='color: red'>(Active)</span>" % obj.last_unbanned
        return obj.last_unbanned
    colored_last_unbanned.allow_tags = True

admin.site.register(CachedTransaction, CachedTransactionAdmin)
admin.site.register(Memo, MemoAdmin)
admin.site.register(IPTracker, IPTrackerAdmin)
