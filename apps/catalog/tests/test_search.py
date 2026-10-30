import pytest
from django.urls import reverse

from apps.inventory import services as stock

from .factories import (
    AttributeFactory,
    BrandFactory,
    CategoryFactory,
    ProductFactory,
    VariantFactory,
)

pytestmark = pytest.mark.django_db


def titles(response):
    return {p.title for p in response.context["products"]}


@pytest.fixture
def catalog():
    watches = CategoryFactory(name="Watches")
    casio = BrandFactory(name="Casio")
    strap = AttributeFactory(name="Strap type")
    strap.categories.add(watches)
    a = ProductFactory(title="Classic steel watch", category=watches, brand=casio, condition="new")
    b = ProductFactory(
        title="Sport watch", category=watches, description="Rubber strap", condition="open_box"
    )
    c = ProductFactory(title="Oak dining table")
    a.attribute_values_set.create(attribute=strap, value="Metal")
    b.attribute_values_set.create(attribute=strap, value="Silicone")
    stock.receive(VariantFactory(product=a, price=9000), 2)
    stock.receive(VariantFactory(product=b, price=4000), 1)
    stock.receive(VariantFactory(product=c, price=40000), 1)
    return watches


def test_search_by_word_and_description(client, catalog):
    url = reverse("catalog:product_list")
    assert titles(client.get(url, {"q": "watch"})) == {"Classic steel watch", "Sport watch"}
    assert titles(client.get(url, {"q": "rubber"})) == {"Sport watch"}
    assert titles(client.get(url, {"q": "casio"})) == {"Classic steel watch"}


def test_price_condition_brand_and_stock_filters(client, catalog):
    url = reverse("catalog:product_list")
    assert titles(client.get(url, {"max_price": 10000})) == {"Classic steel watch", "Sport watch"}
    assert titles(client.get(url, {"min_price": 5000, "max_price": 10000})) == {
        "Classic steel watch"
    }
    assert titles(client.get(url, {"condition": "open_box"})) == {"Sport watch"}
    assert titles(client.get(url, {"brand": "casio"})) == {"Classic steel watch"}


def test_sort_by_price(client, catalog):
    response = client.get(reverse("catalog:product_list"), {"sort": "price_asc"})
    assert [p.title for p in response.context["products"]][0] == "Sport watch"


def test_attribute_filter_on_category_page(client, catalog):
    url = reverse("catalog:category", args=[catalog.slug])
    response = client.get(url, {"attr_strap-type": "Metal"})
    assert titles(response) == {"Classic steel watch"}
    content = response.content.decode()
    assert 'value="Silicone"' in content
    assert 'value="Metal" checked' in content


def test_htmx_returns_only_results(client, catalog):
    response = client.get(reverse("catalog:product_list"), {"q": "watch"}, HTTP_HX_REQUEST="true")
    content = response.content.decode()
    assert content.lstrip().startswith('<div id="results">')
    assert "<html" not in content


def test_pagination_keeps_filters(client, catalog, settings):
    from apps.catalog import views

    views.PAGE_SIZE, old = 1, views.PAGE_SIZE
    try:
        content = client.get(reverse("catalog:product_list"), {"q": "watch"}).content.decode()
    finally:
        views.PAGE_SIZE = old
    assert "?q=watch&amp;page=2" in content


def test_search_leaves_out_products_that_do_not_match(client, catalog):
    # Postgres ranks a row that does not match at 1e-20, not 0.
    other = BrandFactory(name="Philips")
    fryer = ProductFactory(
        title="Philips air fryer", brand=other, description="Air fryer. Checked by our team."
    )
    bank = ProductFactory(
        title="Baseus power bank",
        brand=BrandFactory(name="Baseus"),
        description="Checked by our team.",
    )
    VariantFactory(product=fryer, track_stock=False)
    VariantFactory(product=bank, track_stock=False)
    url = reverse("catalog:product_list")
    assert titles(client.get(url, {"q": "air fryer"})) == {"Philips air fryer"}
