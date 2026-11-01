import datetime
import json

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import PriceTier, Product
from apps.catalog.tests.factories import ProductFactory, VariantFactory
from apps.inventory import lots, services
from apps.inventory.models import Lot

pytestmark = pytest.mark.django_db


def public_lot(reference="DXB-26-01", opens_in=None, **extra):
    opens_at = timezone.now() + datetime.timedelta(hours=opens_in) if opens_in else None
    extra.setdefault("public_title", "Hotel refit")
    return Lot.objects.create(reference=reference, is_public=True, opens_at=opens_at, **extra)


def piece(lot, title="Oak table", quantity=1, price=1000):
    variant = VariantFactory(product=ProductFactory(title=title), price=price)
    services.receive(variant, quantity, lot=lot)
    return variant


def test_lot_gets_a_slug_and_a_page():
    lot = public_lot("DXB 26/01")
    assert lot.slug == "dxb-2601"
    assert lot.get_absolute_url() == "/lots/dxb-2601/"


def test_private_lot_has_no_page(client):
    lot = Lot.objects.create(reference="SECRET-1")
    assert client.get(lot.get_absolute_url()).status_code == 404


def test_pieces_of_a_lot_that_opens_later_stay_hidden(client):
    lot = public_lot(opens_in=48)
    variant = piece(lot, "Brass vase")
    product = variant.product
    assert product not in Product.objects.listed()
    assert client.get(product.get_absolute_url()).status_code == 404
    assert "Brass vase" not in client.get(reverse("catalog:product_list")).content.decode()

    lot.opens_at = timezone.now() - datetime.timedelta(minutes=1)
    lot.save()
    assert product in Product.objects.listed()
    assert client.get(product.get_absolute_url()).status_code == 200


def test_stock_in_an_open_lot_keeps_a_product_listed():
    later, now = public_lot("LATER", opens_in=48), public_lot("NOW")
    variant = piece(later, "Charger", quantity=10)
    services.receive(variant, 5, lot=now)
    assert variant.product in Product.objects.listed()


def test_counts_current_lot_and_next_lot():
    lot = public_lot("OPEN-1")
    piece(lot, "Sofa")
    sold = piece(lot, "Lamp")
    piece(lot, "Table")
    services.reserve(sold, 1)
    upcoming = public_lot("NEXT-1", opens_in=24)
    piece(upcoming, "Sneakers")

    counted = lots.attach_counts([lot])[0]
    assert (counted.items_total, counted.items_left, counted.items_sold) == (3, 2, 1)
    assert counted.left_percent == 67
    assert lots.current_lot() == lot
    assert lots.next_lot() == upcoming
    assert lots.next_lot().items_total == 1


def test_current_lot_skips_a_sold_out_lot():
    done = public_lot("DONE-1", purchase_date=datetime.date(2026, 10, 1))
    services.reserve(piece(done, "Mirror"), 1)
    older = public_lot("OLD-1", purchase_date=datetime.date(2026, 9, 1))
    piece(older, "Chair")
    assert lots.current_lot() == older
    assert lots.past_lots() == [done]


def test_home_shows_the_lot_and_the_next_one(client):
    lot = public_lot("DXB-26-07")
    piece(lot, "Velvet armchair")
    upcoming = public_lot("DXB-26-08", opens_in=30, public_title="Sneaker surplus")
    piece(upcoming, "Hidden sneakers")
    content = client.get(reverse("core:home")).content.decode()
    assert "DXB-26-07" in content
    assert "Velvet armchair" in content
    assert "Sneaker surplus" in content
    assert 'x-data="countdown(' in content
    assert reverse("lots:calendar", args=[upcoming.slug]) in content
    assert "Hidden sneakers" not in content


def test_lot_page_filters_with_chips(client):
    lot = public_lot()
    piece(lot, "Cheap cable", price=650)
    piece(lot, "Dear sofa", price=85000)
    url = lot.get_absolute_url()
    content = client.get(url).content.decode()
    assert "Cheap cable" in content and "Dear sofa" in content

    response = client.get(url, {"f": "under"}, HTTP_HX_REQUEST="true")
    content = response.content.decode()
    assert content.lstrip().startswith('<div id="lot-grid"')
    assert "Cheap cable" in content and "Dear sofa" not in content


def test_bulk_chip_shows_only_public_tiers(client):
    lot = public_lot()
    bulk = piece(lot, "Bulk charger", quantity=50)
    PriceTier.objects.create(variant=bulk, min_quantity=10, unit_price=800)
    wholesale = piece(lot, "Trade cable", quantity=50)
    PriceTier.objects.create(
        variant=wholesale, min_quantity=10, unit_price=400, wholesale_only=True
    )
    content = client.get(lot.get_absolute_url(), {"f": "bulk"}).content.decode()
    assert "Bulk charger" in content and "Trade cable" not in content


def test_upcoming_lot_page_shows_a_countdown_not_pieces(client):
    lot = public_lot(opens_in=5)
    piece(lot, "Secret sneakers")
    content = client.get(lot.get_absolute_url()).content.decode()
    assert "Secret sneakers" not in content
    assert 'x-data="countdown(' in content
    assert client.get(reverse("lots:dig", args=[lot.slug])).status_code == 404


def test_dig_page_has_the_pieces_as_json(client):
    lot = public_lot()
    variant = piece(lot, "Fossil watch", quantity=2)
    content = client.get(reverse("lots:dig", args=[lot.slug])).content.decode()
    data = json.loads(
        content.split('id="dig-data" type="application/json">')[1].split("</script>")[0]
    )
    item = data["items"][0]
    assert item["title"] == "Fossil watch"
    assert item["left"] == "2 left"
    assert item["save_url"] == reverse("catalog:saved_toggle", args=[variant.product_id])
    assert item["saved"] is False


def test_calendar_file_for_the_opening(client):
    lot = public_lot("DXB-26-09", opens_in=24)
    response = client.get(reverse("lots:calendar", args=[lot.slug]))
    content = response.content.decode()
    assert response["Content-Type"] == "text/calendar"
    assert "BEGIN:VEVENT" in content
    assert lot.opens_at.astimezone(datetime.UTC).strftime("DTSTART:%Y%m%dT%H%M%SZ") in content
    assert "SUMMARY:Lot DXB-26-09 opens" in content


def test_lot_list_groups_lots(client):
    piece(public_lot("OPEN-9"), "Lamp")
    public_lot("SOON-9", opens_in=10)
    content = client.get(reverse("lots:list")).content.decode()
    assert "Open now" in content and "OPEN-9" in content
    assert "Opening soon" in content and "SOON-9" in content


def test_product_page_shows_its_lot_and_more_from_it(client):
    lot = public_lot("DXB-26-10")
    variant = piece(lot, "Oak desk")
    piece(lot, "Desk lamp")
    content = client.get(variant.product.get_absolute_url()).content.decode()
    assert "DXB-26-10" in content
    assert "More from lot DXB-26-10" in content
    assert "Desk lamp" in content
