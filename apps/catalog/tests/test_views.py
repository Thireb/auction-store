import pytest
from django.urls import reverse

from .factories import AttributeFactory, CategoryFactory, ProductFactory, VariantFactory

pytestmark = pytest.mark.django_db


def test_product_list_shows_only_visible_products(client):
    VariantFactory(track_stock=False, product=ProductFactory(title="Oak table"))
    VariantFactory(track_stock=False, product=ProductFactory(title="Hidden lamp", is_active=False))
    content = client.get(reverse("catalog:product_list")).content.decode()
    assert "Oak table" in content
    assert "Hidden lamp" not in content


def test_category_page_includes_subcategory_products(client):
    watches = CategoryFactory(name="Watches")
    smart = CategoryFactory(name="Smart watches", parent=watches)
    VariantFactory(track_stock=False, product=ProductFactory(title="Fitness band", category=smart))
    VariantFactory(track_stock=False, product=ProductFactory(title="Office chair"))
    content = client.get(reverse("catalog:category", args=[watches.slug])).content.decode()
    assert "Fitness band" in content
    assert "Office chair" not in content
    assert "Smart watches" in content


def test_inactive_category_is_404(client):
    category = CategoryFactory(is_active=False)
    assert client.get(reverse("catalog:category", args=[category.slug])).status_code == 404


def test_product_detail(client):
    product = ProductFactory(title="Analog watch", description="Steel case")
    strap = AttributeFactory(name="Strap")
    strap.categories.add(product.category)
    product.attribute_values_set.create(attribute=strap, value="Leather")
    VariantFactory(track_stock=False, product=product, name="Black", price=4500)
    VariantFactory(track_stock=False, product=product, name="Silver", price=4800)
    response = client.get(reverse("catalog:product", args=[product.slug]))
    content = response.content.decode()
    assert response.status_code == 200
    assert "Rs 4,500" in content
    assert "Leather" in content
    assert 'id="variant-select"' in content


def test_hidden_product_is_404(client):
    product = ProductFactory(is_active=False)
    assert client.get(reverse("catalog:product", args=[product.slug])).status_code == 404


def test_home_shows_featured_and_menu(client):
    category = CategoryFactory(name="Furniture")
    VariantFactory(
        track_stock=False,
        product=ProductFactory(title="Featured sofa", is_featured=True, category=category),
    )
    content = client.get(reverse("core:home")).content.decode()
    assert "Featured sofa" in content
    assert category.get_absolute_url() in content


def test_list_query_count_does_not_grow(client, django_assert_max_num_queries):
    for _ in range(10):
        VariantFactory(track_stock=False)
    with django_assert_max_num_queries(10):
        client.get(reverse("catalog:product_list"))
