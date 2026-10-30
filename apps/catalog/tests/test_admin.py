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
        "variants-TOTAL_FORMS": "1",
        "variants-INITIAL_FORMS": "1",
        "variants-MIN_NUM_FORMS": "1",
        "variants-MAX_NUM_FORMS": "1000",
        "variants-0-id": variant.pk,
        "variants-0-product": product.pk,
        "variants-0-sku": variant.sku,
        "variants-0-price": "2500",
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
