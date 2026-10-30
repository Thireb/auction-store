from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.demo import seed_catalog
from apps.core.demo import seed_pages
from apps.inventory.demo import seed_inventory
from apps.shipping.demo import seed_shipping


class Command(BaseCommand):
    help = "Add demo data for local tests. Safe to run again: it skips data that exists."

    @transaction.atomic
    def handle(self, *args, **options):
        seed_catalog(self.stdout)
        seed_inventory(self.stdout)
        seed_shipping(self.stdout)
        seed_pages(self.stdout)
        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
