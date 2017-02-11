import requests
import urllib
import datetime

from django.utils import timezone
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from multiexplorer.models import PushHistory, Memo

class Command(BaseCommand):
    help = 'Perform pushing of memos from another memo server.'

    def handle(self, *args, **options):
        if settings.MEMO_SERVER_PRIVATE_MODE:
            self.stderr.write(self.style.NOTICE('Private Mode is enabled. Not pushing.'))
            return

        history, created = PushHistory.objects.get_or_create()
        memos = Memo.objects.filter(created__gte=history.last_pushed).exclude(signature='')

        for push_url in settings.MEMO_SERVER_PUSH:
            for memo in memos:
                try:
                    response = requests.post(push_url, data=memo.as_dict())
                except Exception as exc:
                    self.stderr.write(
                        self.style.ERROR('Failed to push to %s: %s' % (
                            push_url, exc
                        ))
                    )

        history.last_pushed = timezone.now()
        history.save()

        self.stdout.write(
            self.style.SUCCESS('Push Complete. Pushed %s memos to %s servers.' % (
                len(memos), len(settings.MEMO_SERVER_PUSH)
            ))
        )
