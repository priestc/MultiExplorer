from django.core.management.base import BaseCommand, CommandError
from upcoin.models import Peer

class Command(BaseCommand):
    help = 'Starts the consensus process. Called every 10 minutes.'

    def handle(self, *args, **options):
        ledger_hash = LedgerEntry.ledger_hash()
        peers = Peer.shuffle(ledger_hash)
        
