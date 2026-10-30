from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Product
from apps.inventory import services

from .factories import ProductFactory, VariantFactory

pytestmark = pytest.mark.django_db


def test_last_piece_dispatched_sets_sold_out_and_restock_clears_it():
    variant = VariantFactory()
    services.receive(variant, 1)
    services.reserve(variant, 1)
    product = Product.objects.get(pk=variant.product_id)
    assert product.sold_out_at is not None
    services.release(variant, 1)
    product.refresh_from_db()
    assert product.sold_out_at is None


def test_product_with_one_variant_left_is_not_sold_out():
    product = ProductFactory()
    a, b = VariantFactory(product=product), VariantFactory(product=product)
    services.receive(a, 1)
    services.receive(b, 1)
    services.reserve(a, 1)
    product.refresh_from_db()
    assert product.sold_out_at is None
    assert not product.is_sold_out


def test_sold_out_product_is_listed_with_badge_then_hidden(client, settings):
    settings.SOLD_OUT_LISTED_DAYS = 7
    variant = VariantFactory(product=ProductFactory(title="Antique mirror"))
    services.receive(variant, 1)
    services.reserve(variant, 1)
    content = client.get(reverse("catalog:product_list")).content.decode()
    assert "Antique mirror" in content
    assert ">Sold<" in content

    Product.objects.update(sold_out_at=timezone.now() - timedelta(days=8))
    content = client.get(reverse("catalog:product_list")).content.decode()
    assert "Antique mirror" not in content
    # A shared link still opens the product page.
    assert client.get(variant.product.get_absolute_url()).status_code == 200
