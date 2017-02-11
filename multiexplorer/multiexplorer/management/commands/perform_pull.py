import requests
import urllib
import datetime

from django.utils import timezone
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from multiexplorer.models import PullHistory

class Command(BaseCommand):
    help = 'Perform pulling of memos from another memo server.'

    def handle(self, *args, **options):
        for pull_url in settings.MEMO_SERVER_PULL:
            history, created = PullHistory.objects.get_or_create(pull_url=pull_url)

            if created:
                s = timzone.now() - datetime.timedelta(hours=3)
            else:
                s = history.last_pulled

            since = urllib.urlencode({'since': s})
            try:
                response = requests.get("%s?%s" % (pull_url, since)).json()
            except:
                self.stderr.write(
                    self.style.ERROR('Failed to fetch from %s' % pull_url)
                )
                continue

            history.last_pulled = timezone.now()
            memos = response['memos']

            for data in memos:
                memo, created = Memo.objects.get_or_create(
                    txid=data['x'],
                    crypto=data['c'],
                    pubkey=data['p']
                )
                memo.encrypted_text = data['t']
                memo.save()

            history.save()

            self.stdout.write(
                self.style.SUCCESS('Pull Complete. Got %s memos from %s' % (len(memos), pull_url))
            )
