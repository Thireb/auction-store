import pytest
from django.contrib.auth import get_user_model
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


@pytest.mark.django_db
def test_seed_demo_adds_people_and_orders_once(settings, tmp_path):
    from apps.accounts.models import WholesaleProfile
    from apps.orders.models import Order

    settings.MEDIA_ROOT = tmp_path
    call_command("seed_demo")
    orders = Order.objects.count()
    call_command("seed_demo")
    assert Product.objects.count() > 150
    assert orders > 30
    assert Order.objects.count() == orders
    assert len(set(Order.objects.values_list("status", flat=True))) >= 6
    assert WholesaleProfile.objects.filter(status=WholesaleProfile.APPROVED).exists()
    staff = get_user_model().objects.filter(username__startswith="demo-")
    assert staff.count() == 2
    assert not any(u.has_usable_password() for u in get_user_model().objects.all())


@pytest.mark.django_db
def test_setup_store_adds_no_products():
    from apps.core.models import Page
    from apps.shipping.models import City, ShippingSettings

    call_command("setup_store")
    call_command("setup_store")
    assert City.objects.count() > 50
    assert Page.objects.count() == 4
    assert ShippingSettings.objects.count() == 1
    assert not Product.objects.exists()
