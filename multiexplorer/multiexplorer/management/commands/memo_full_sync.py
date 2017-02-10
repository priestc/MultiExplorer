from __future__ import print_function
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from multiexplorer.models import PullHistory

import requests
import urllib

class Command(BaseCommand):
    help = 'Perform pulling of memos from another memo server.'

    def handle(self, *args, **options):
        for i, pull_url in enumerate(settings.MEMO_SERVER_PULL, 1):
            print("%s - %s" % (i, pull_url))

        choice = int(raw_input("Choose which pull server to perform full sync from: "))
        pull_url = settings.MEMO_SERVER_PULL[choice-1]

        total_count = 0
        page = 1
        while True:
            pull_url = "%s?%s" % (pull_url, urllib.urlencode({'page': page}))

            response = requests.get(pull_url).json()
            for data in response['memos']:
                memo, created = Memo.objects.get_or_create(
                    txid=data['x'],
                    crypto=data['c'],
                    pubkey=data['p']
                )
                memo.encrypted_text = data['t']
                memo.save()

            count = len(response)
            if count < 100:
                break

            total_count += count
            page += 1

        self.stdout.write(
            self.style.SUCCESS('Full sync of %s complete. (%s memos)' % (pull_url, total_count))
        )
