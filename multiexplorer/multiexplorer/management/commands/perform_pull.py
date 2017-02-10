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
                since = timzone.now() - datetime.timedelta(hours=3)
            else:
                since = urllib.urlencode({'since': history.last_pulled})
                try:
                    response = requests.get("%s?%s" % (pull_url, since)).json()
                except:
                    self.stderr.write(
                        self.style.ERROR('Failed to fetch from %s' % pull_url)
                    )
                    continue

                for data in response:
                    memo, created = Memo.objects.get_or_create(
                        txid=data['x'],
                        crypto=data['c'],
                        pubkey=data['p']
                    )
                    memo.encrypted_text = data['t']
                    memo.save()


            history.last_pulled = timezone.now()
            history.save()

            self.stdout.write(
                self.style.SUCCESS('Got %s memos from %s' % (len(response), pull_url))
            )
