import pytest
from django.core.management import call_command

from apps.catalog.models import Category, Product


@pytest.mark.django_db
def test_seed_demo_runs_twice_without_duplicates(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    call_command("seed_demo")
    products, categories = Product.objects.count(), Category.objects.count()
    call_command("seed_demo")
    assert products > 10
    assert Product.objects.count() == products
    assert Category.objects.count() == categories
    assert all(p.variants.exists() and p.images.exists() for p in Product.objects.all())
