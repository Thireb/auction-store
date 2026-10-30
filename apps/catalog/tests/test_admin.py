import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.catalog.models import Attribute, Product

from .factories import AttributeFactory, CategoryFactory, ProductFactory, VariantFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner_client(client):
    owner = get_user_model().objects.create_superuser("owner", "o@example.com", "pass")
    client.force_login(owner)
    return client


def test_product_form_shows_category_attributes(owner_client):
    category = CategoryFactory()
    strap = AttributeFactory(name="Strap type", type=Attribute.CHOICE, choices="Leather\nMetal")
    strap.categories.add(category)
    product = ProductFactory(category=category)
    VariantFactory(product=product)
    response = owner_client.get(reverse("admin:catalog_product_change", args=[product.pk]))
    assert response.status_code == 200
    assert f'name="attr_{strap.pk}"' in response.content.decode()


def test_product_form_saves_attribute_values(owner_client):
    category = CategoryFactory()
    strap = AttributeFactory(name="Strap type", type=Attribute.CHOICE, choices="Leather\nMetal")
    strap.categories.add(category)
    product = ProductFactory(category=category, title="Watch")
    variant = VariantFactory(product=product)
    data = {
        "title": "Watch",
        "slug": product.slug,
        "category": category.pk,
        "condition": "new",
        "is_active": "on",
        f"attr_{strap.pk}": "Metal",
        "advance_value": "0",
        "variants-TOTAL_FORMS": "1",
        "variants-INITIAL_FORMS": "1",
        "variants-MIN_NUM_FORMS": "1",
        "variants-MAX_NUM_FORMS": "1000",
        "variants-0-id": variant.pk,
        "variants-0-product": product.pk,
        "variants-0-sku": variant.sku,
        "variants-0-price": "2500",
        "variants-0-min_order_qty": "1",
        "variants-0-order_step": "1",
        "variants-0-track_stock": "on",
        "variants-0-is_active": "on",
        "variants-0-sort_order": "0",
        "images-TOTAL_FORMS": "0",
        "images-INITIAL_FORMS": "0",
        "images-MIN_NUM_FORMS": "0",
        "images-MAX_NUM_FORMS": "1000",
    }
    url = reverse("admin:catalog_product_change", args=[product.pk])
    response = owner_client.post(url, data)
    assert response.status_code == 302, response.context["adminform"].form.errors
    product.refresh_from_db()
    assert product.attribute_values() == [(strap, "Metal")]

    data[f"attr_{strap.pk}"] = ""
    owner_client.post(url, data)
    assert product.attribute_values() == []


def test_staff_cannot_delete_products(client):
    staff = get_user_model().objects.create_user("staff", password="pass", is_staff=True)
    from django.contrib.auth.models import Permission

    staff.user_permissions.add(*Permission.objects.filter(content_type__app_label="catalog"))
    client.force_login(staff)
    product = ProductFactory()
    response = client.post(
        reverse("admin:catalog_product_delete", args=[product.pk]), {"post": "yes"}
    )
    assert response.status_code == 403
    assert Product.objects.filter(pk=product.pk).exists()


@pytest.mark.parametrize(
    "name", ["catalog_product", "catalog_category", "catalog_attribute", "catalog_brand"]
)
def test_admin_pages_load(owner_client, name):
    VariantFactory()
    assert owner_client.get(reverse(f"admin:{name}_changelist")).status_code == 200
    assert owner_client.get(reverse(f"admin:{name}_add")).status_code == 200


def test_staff_without_price_permission_cannot_change_price(client):
    from django.contrib.auth.models import Permission

    staff = get_user_model().objects.create_user("inv", password="x", is_staff=True)
    staff.user_permissions.add(
        *Permission.objects.filter(codename__in=["change_variant", "view_variant"])
    )
    client.force_login(staff)
    variant = VariantFactory(price=1000)
    url = reverse("admin:catalog_variant_change", args=[variant.pk])
    data = {
        "product": variant.product.pk,
        "sku": variant.sku,
        "price": "800",
        "min_order_qty": 1,
        "order_step": 1,
        "low_stock_threshold": 2,
        "is_active": "on",
        "track_stock": "on",
        "sort_order": 0,
        "price_tiers-TOTAL_FORMS": "0",
        "price_tiers-INITIAL_FORMS": "0",
        "price_tiers-MIN_NUM_FORMS": "0",
        "price_tiers-MAX_NUM_FORMS": "1000",
    }
    response = client.post(url, data)
    assert response.status_code == 200
    assert "permission to change prices" in response.content.decode()

    staff.user_permissions.add(Permission.objects.get(codename="change_price"))
    response = client.post(url, data)
    assert response.status_code == 302
    variant.refresh_from_db()
    assert variant.price == 800
