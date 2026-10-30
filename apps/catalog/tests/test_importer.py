import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.catalog.importer import import_csv, template_csv
from apps.catalog.models import Product, Variant
from apps.inventory.models import Lot, StockItem

from .factories import AttributeFactory, CategoryFactory, VariantFactory

pytestmark = pytest.mark.django_db

HEADER = "title,category,brand,condition,sku,variant,price,quantity,lot,cost_per_unit,attr:Color\n"


@pytest.fixture
def cables():
    parent = CategoryFactory(name="Mobile accessories")
    return CategoryFactory(name="Cables", parent=parent)


def csv_file(text):
    return io.BytesIO(text.encode("utf-8"))


def test_import_creates_products_variants_stock_and_attributes(cables):
    AttributeFactory(name="Color")
    data = HEADER + (
        "USB-C cable,Mobile accessories > Cables,Baseus,new,CAB-1,Black,650,100,L-1,300,Black\n"
        "USB-C cable,Mobile accessories > Cables,Baseus,new,CAB-2,White,650,50,L-1,300,\n"
    )
    result = import_csv(csv_file(data), user=None, dry_run=False)
    assert result.errors == []
    assert (result.products_created, result.variants_created, result.stock_rows) == (1, 2, 2)
    product = Product.objects.get(title="USB-C cable")
    assert product.variants.count() == 2
    assert product.brand.name == "Baseus"
    assert product.attribute_values()[0][1] == "Black"
    assert Variant.objects.get(sku="CAB-1").stock_on_hand == 100
    assert StockItem.objects.get(variant__sku="CAB-1").lot == Lot.objects.get(reference="L-1")


def test_dry_run_saves_nothing(cables):
    data = HEADER + "USB-C cable,Mobile accessories > Cables,,new,CAB-1,,650,10,,,\n"
    result = import_csv(csv_file(data), user=None, dry_run=True)
    assert result.ok and result.variants_created == 1
    assert not Variant.objects.exists()


def test_one_bad_row_imports_nothing(cables):
    data = HEADER + (
        "Good,Mobile accessories > Cables,,new,OK-1,,650,10,,,\n"
        "Bad,Mobile accessories > Wires,,new,BAD-1,,650,10,,,\n"
    )
    result = import_csv(csv_file(data), user=None, dry_run=False)
    assert result.errors == [
        (3, "Category 'Mobile accessories > Wires' does not exist. Add it in the admin first.")
    ]
    assert not Product.objects.exists()


def test_existing_sku_only_adds_stock(cables):
    variant = VariantFactory(sku="OLD-1", price=900)
    data = HEADER + "Other title,Mobile accessories > Cables,,new,OLD-1,,1,5,,,\n"
    result = import_csv(csv_file(data), user=None, dry_run=False)
    assert result.ok and result.variants_created == 0
    variant.refresh_from_db()
    assert (variant.price, variant.stock_on_hand) == (900, 5)


def test_missing_columns():
    result = import_csv(csv_file("title,sku\nA,B\n"), user=None)
    assert result.errors == [(1, "Missing columns: category, price.")]


def test_template_has_required_columns():
    header = template_csv().splitlines()[0]
    for column in ["title", "category", "sku", "price"]:
        assert column in header


def test_admin_import_view(client, cables):
    owner = get_user_model().objects.create_superuser("owner", "o@example.com", "x")
    client.force_login(owner)
    url = reverse("admin:catalog_product_import")
    assert client.get(url).status_code == 200
    assert client.get(url + "?template=1")["Content-Type"] == "text/csv"
    upload = SimpleUploadedFile(
        "p.csv", (HEADER + "Cable,Mobile accessories > Cables,,new,C-1,,650,3,,,\n").encode()
    )
    response = client.post(url, {"file": upload})
    assert "Imported" in response.content.decode()
    assert Variant.objects.get(sku="C-1").stock_on_hand == 3


def test_bad_price_is_reported(cables):
    data = HEADER + "Bad,Mobile accessories > Cables,,new,BAD-1,,abc,10,,,\n"
    result = import_csv(csv_file(data), user=None)
    assert result.errors == [(2, "price must be a number, not 'abc'.")]
