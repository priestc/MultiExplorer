from django.core.management.base import BaseCommand, CommandError
from pricetick.models import get_ticks

class Command(BaseCommand):
    args = '<poll_id poll_id ...>'
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        self.stdout.write(str(get_ticks()))
