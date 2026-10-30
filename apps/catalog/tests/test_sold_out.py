import pytest
from django.urls import reverse

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


def test_out_of_stock_product_is_hidden_from_customers(client):
    variant = VariantFactory(product=ProductFactory(title="Antique mirror"))
    url = variant.product.get_absolute_url()
    # Never stocked: not shown.
    assert "Antique mirror" not in client.get(reverse("catalog:product_list")).content.decode()
    assert client.get(url).status_code == 404

    services.receive(variant, 1)
    assert "Antique mirror" in client.get(reverse("catalog:product_list")).content.decode()
    assert client.get(url).status_code == 200
    search = client.get(reverse("catalog:product_list"), {"q": "mirror"}).content.decode()
    assert "Antique mirror" in search

    # The last piece is reserved by an order: gone from lists, search and its page.
    services.reserve(variant, 1)
    assert "Antique mirror" not in client.get(reverse("catalog:product_list")).content.decode()
    search = client.get(reverse("catalog:product_list"), {"q": "mirror"}).content.decode()
    assert "Antique mirror" not in search
    assert client.get(url).status_code == 404
    assert Product.objects.listed().count() == 0
    assert Product.objects.out_of_stock().count() == 1


def test_untracked_variant_is_always_listed():
    VariantFactory(track_stock=False)
    assert Product.objects.listed().count() == 1
