import datetime
import io

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.catalog.models import ProductImage
from apps.catalog.tests.factories import ProductFactory, VariantFactory
from apps.core.management.commands.setup_roles import Command as SetupRoles
from apps.core.roles import INVENTORY_MANAGER
from apps.inventory import photos, services
from apps.inventory.models import Lot, LotPhoto

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def staff():
    SetupRoles().handle()
    user = User.objects.create_user("stock", password="pass-1234", is_staff=True)
    user.groups.add(Group.objects.get(name=INVENTORY_MANAGER))
    return user


@pytest.fixture
def owner():
    return User.objects.create_superuser("owner", "o@example.com", "pass")


def jpeg(name="IMG_0001.jpg", size=(3000, 2000)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "teal").save(buffer, "JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


def tray_photo(lot=None, user=None, name="IMG_0001.jpg"):
    return photos.add_photo(lot, jpeg(name, (800, 600)), user)


def test_upload_shrinks_the_photo_and_makes_a_thumbnail(staff):
    lot = Lot.objects.create(reference="DXB-1")
    photo = photos.add_photo(lot, jpeg(), staff)
    assert photo.status == LotPhoto.UNASSIGNED
    assert photo.original_name == "IMG_0001.jpg" and photo.uploaded_by == staff
    with Image.open(photo.image.path) as big, Image.open(photo.thumbnail.path) as small:
        assert max(big.size) == photos.MAX_SIDE
        assert max(small.size) == photos.THUMB_SIDE


def test_upload_refuses_a_file_that_is_not_a_photo(staff):
    with pytest.raises(ValidationError):
        photos.add_photo(None, SimpleUploadedFile("notes.jpg", b"not a photo"), staff)


def test_assign_puts_photos_on_the_item_in_order(staff):
    product = ProductFactory()
    first, second = tray_photo(name="a.jpg"), tray_photo(name="b.jpg")
    images = photos.assign([second.pk, first.pk], product, staff)
    assert [i.source_photo for i in images] == [second, first]
    assert [i.sort_order for i in images] == [0, 1]
    assert images[0].image.name == second.image.name  # The same file, no copy.
    second.refresh_from_db()
    assert second.status == LotPhoto.ASSIGNED and second.assigned_by == staff


def test_a_used_photo_cannot_go_on_a_second_item(staff):
    photo = tray_photo()
    photos.assign([photo.pk], ProductFactory(), staff)
    with pytest.raises(photos.TrayError):
        photos.assign([photo.pk], ProductFactory(), staff)


def test_use_again_lets_the_photo_go_on_one_more_item(staff):
    photo = tray_photo()
    photos.assign([photo.pk], ProductFactory(), staff)
    photo.refresh_from_db()
    photos.use_again(photo, staff)
    assert photo in LotPhoto.objects.pickable()
    photos.assign([photo.pk], ProductFactory(), staff)
    photo.refresh_from_db()
    assert photo.uses.count() == 2 and not photo.reusable
    assert photo not in LotPhoto.objects.pickable()


def test_removing_a_photo_from_an_item_returns_it_to_the_tray(staff):
    photo = tray_photo()
    image = photos.assign([photo.pk], ProductFactory(), staff)[0]
    photos.remove_image(image, staff)
    photo.refresh_from_db()
    assert photo.status == LotPhoto.UNASSIGNED and photo.assigned_by is None
    assert not ProductImage.objects.exists()


def test_not_usable_and_only_the_owner_deletes(staff, owner):
    photo = tray_photo()
    photos.mark_not_usable(photo, staff)
    assert photo.status == LotPhoto.NOT_USABLE
    with pytest.raises(PermissionDenied):
        photos.delete_photo(photo, staff)
    photos.delete_photo(photo, owner)
    assert not LotPhoto.objects.exists()


def test_counts_flag_old_unassigned_photos(staff):
    old, new = tray_photo(), tray_photo()
    LotPhoto.objects.filter(pk=old.pk).update(
        uploaded_at=timezone.now() - datetime.timedelta(days=8)
    )
    photos.assign([new.pk], ProductFactory(), staff)
    numbers = photos.counts(LotPhoto.objects.all())
    assert numbers == {"total": 2, "unassigned": 1, "assigned": 1, "not_usable": 0, "old": 1}


# Staff portal ---------------------------------------------------------------------------


def test_upload_endpoint_adds_one_photo(client, staff):
    lot = Lot.objects.create(reference="DXB-2")
    client.force_login(staff)
    response = client.post(reverse("portal:tray_upload", args=[lot.pk]), {"photo": jpeg()})
    assert response.status_code == 200
    photo = LotPhoto.objects.get()
    assert response.json()["id"] == photo.pk and photo.lot == lot
    bad = client.post(reverse("portal:tray_upload", args=["none"]), {})
    assert bad.status_code == 400


def test_tray_page_shows_counts_and_items_without_photos(client, staff):
    lot = Lot.objects.create(reference="DXB-3")
    variant = VariantFactory(product=ProductFactory(title="Brass lamp"))
    services.receive(variant, 1, lot=lot)
    tray_photo(lot)
    client.force_login(staff)
    content = client.get(reverse("portal:tray_detail", args=[lot.pk])).content.decode()
    assert "1 photo: 1 unassigned, 0 assigned, 0 not usable." in content
    assert "Brass lamp" in content.split('id="items-without-photos"')[1]
    assert 'id="tray-upload"' in content


def test_pick_page_assigns_photos_and_returns_to_the_item(client, staff):
    lot = Lot.objects.create(reference="DXB-4")
    variant = VariantFactory()
    services.receive(variant, 1, lot=lot)
    a, b = tray_photo(lot, name="a.jpg"), tray_photo(lot, name="b.jpg")
    client.force_login(staff)
    url = reverse("portal:pick_photos", args=[variant.product_id])
    content = client.get(url).content.decode()
    assert f'aria-label="Photo {a}"' in content  # The item's lot tray opens first.
    response = client.post(f"{url}?tray={lot.pk}", {"photo": [b.pk, a.pk]})
    assert response.url.endswith("#photos")
    assert list(variant.product.images.values_list("source_photo", flat=True)) == [b.pk, a.pk]
    # Picked photos leave the picker.
    assert f'aria-label="Photo {a}"' not in client.get(f"{url}?tray={lot.pk}").content.decode()


def test_pick_page_reports_a_photo_someone_else_took(client, staff):
    photo = tray_photo()
    photos.assign([photo.pk], ProductFactory(), staff)
    product = ProductFactory()
    client.force_login(staff)
    url = reverse("portal:pick_photos", args=[product.pk])
    response = client.post(f"{url}?tray=none", {"photo": [photo.pk]}, follow=True)
    assert "already used" in response.content.decode()
    assert not product.images.exists()


def test_photo_actions_from_the_tray(client, staff, owner):
    photo = tray_photo()
    client.force_login(staff)
    client.post(reverse("portal:photo_action", args=[photo.pk, "not_usable"]))
    photo.refresh_from_db()
    assert photo.status == LotPhoto.NOT_USABLE
    client.post(reverse("portal:photo_action", args=[photo.pk, "delete"]))
    assert LotPhoto.objects.filter(pk=photo.pk).exists()  # Staff cannot delete.
    client.force_login(owner)
    client.post(reverse("portal:photo_action", args=[photo.pk, "delete"]))
    assert not LotPhoto.objects.filter(pk=photo.pk).exists()


def test_dashboard_shows_old_unassigned_photos(client, staff):
    photo = tray_photo()
    LotPhoto.objects.filter(pk=photo.pk).update(
        uploaded_at=timezone.now() - datetime.timedelta(days=10)
    )
    client.force_login(staff)
    content = client.get(reverse("portal:dashboard")).content.decode()
    assert 'id="photos-waiting"' in content


# Store ---------------------------------------------------------------------------------


def test_store_shows_the_default_photo_for_an_item_without_one(client):
    variant = VariantFactory(product=ProductFactory(title="Bare item"), track_stock=False)
    content = client.get(reverse("catalog:product_list")).content.decode()
    assert "store/no-photo.svg" in content
    assert "store/no-photo.svg" in client.get(variant.product.get_absolute_url()).content.decode()
