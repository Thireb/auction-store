from django.core.management.base import BaseCommand

from apps.shipping.cities import load_cities


class Command(BaseCommand):
    help = "Add the main Pakistani cities for delivery. Safe to run again."

    def handle(self, *args, **options):
        self.stdout.write(f"Added {load_cities()} cities.")
