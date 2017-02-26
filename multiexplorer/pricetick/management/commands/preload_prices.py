from django.core.management.base import BaseCommand, CommandError
from pricetick.models import load_all

class Command(BaseCommand):
    args = '<poll_id poll_id ...>'
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        load_all()
