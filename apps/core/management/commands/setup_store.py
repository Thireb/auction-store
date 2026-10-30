from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.demo import seed_pages
from apps.shipping.cities import load_cities
from apps.shipping.models import ShippingSettings


class Command(BaseCommand):
    help = "Prepare a new live store: cities, starter pages and default settings. No demo products."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(f"Added {load_cities()} cities.")
        seed_pages(self.stdout)
        ShippingSettings.load()
        self.stdout.write(
            self.style.SUCCESS(
                "Done. Now set the fees and payment details in the staff portal: /staff/settings/."
            )
        )
