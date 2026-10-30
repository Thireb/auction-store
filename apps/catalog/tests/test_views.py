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


def test_sidebar_opens_branch_of_current_category(client):
    watches = CategoryFactory(name="Watches")
    smart = CategoryFactory(name="Smart watches", parent=watches)
    CategoryFactory(name="Fitness bands", parent=smart)
    furniture = CategoryFactory(name="Furniture")
    CategoryFactory(name="Sofas", parent=furniture)
    content = client.get(reverse("catalog:category", args=[smart.slug])).content.decode()
    assert 'id="category-nav"' in content
    # The branch of the current category is rendered, other branches load on demand.
    assert "Fitness bands" in content
    assert "Sofas" not in content
    assert f'hx-get="{reverse("catalog:nav_children", args=[furniture.pk])}"' in content
    assert 'aria-current="page"' in content


def test_sidebar_loads_children_and_searches(client):
    furniture = CategoryFactory(name="Furniture")
    CategoryFactory(name="Sofas", parent=furniture)
    CategoryFactory(name="Hidden beds", parent=furniture, is_active=False)
    content = client.get(
        reverse("catalog:nav_children", args=[furniture.pk]), HTTP_HX_REQUEST="true"
    ).content.decode()
    assert "Sofas" in content and "Hidden beds" not in content
    assert "<html" not in content
    content = client.get(reverse("catalog:nav_search"), {"q": "sof"}).content.decode()
    assert "Sofas" in content and "in Furniture" in content


def test_product_page_opens_its_category_in_sidebar(client):
    parent = CategoryFactory(name="Mobile accessories")
    child = CategoryFactory(name="Chargers", parent=parent)
    CategoryFactory(name="Cables", parent=parent)
    variant = VariantFactory(track_stock=False, product=ProductFactory(category=child))
    content = client.get(variant.product.get_absolute_url()).content.decode()
    assert "Cables" in content
