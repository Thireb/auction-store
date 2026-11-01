"""Lot photo trays: staff upload many photos, then put them on items one by one.

All tray changes go through these functions. Each one writes the history (who, when).
"""

import datetime
import io
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from apps.catalog.models import ProductImage

from .models import LotPhoto

# Phone photos are large. The browser already makes them smaller; this is the server limit.
MAX_SIDE = 2000
THUMB_SIDE = 480
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
OLD_AFTER_DAYS = 7


class TrayError(Exception):
    """A tray action that cannot happen, with a message for staff."""


def _jpeg(image, side, quality):
    copy = image.copy()
    copy.thumbnail((side, side))
    out = io.BytesIO()
    copy.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
    return out.getvalue()


def add_photo(lot, upload, user):
    """Save one uploaded photo in `lot`'s tray (None: the "No lot" tray)."""
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError("This photo is larger than 15 MB.")
    try:
        image = Image.open(upload)
        image = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError("This file is not a photo we can read.") from exc
    stem = Path(upload.name).stem[:60] or "photo"
    photo = LotPhoto(lot=lot, original_name=upload.name[:255], uploaded_by=user)
    photo.image.save(f"{stem}.jpg", ContentFile(_jpeg(image, MAX_SIDE, 85)), save=False)
    photo.thumbnail.save(f"{stem}.jpg", ContentFile(_jpeg(image, THUMB_SIDE, 75)), save=False)
    photo.save()
    return photo


@transaction.atomic
def assign(photo_ids, product, user):
    """Put tray photos on `product`, in the given order. Return the new ProductImages.

    A photo that someone else just used (and that is not marked "use again") stops the
    whole action, so staff can pick again.
    """
    ids = [int(pk) for pk in photo_ids]
    photos = {p.pk: p for p in LotPhoto.objects.select_for_update().filter(pk__in=ids)}
    if not ids or any(pk not in photos or not _can_pick(photos[pk]) for pk in ids):
        raise TrayError("A photo you picked is already used. Pick again.")
    start = (product.images.aggregate(n=Max("sort_order"))["n"] or -1) + 1
    now, created = timezone.now(), []
    for n, pk in enumerate(dict.fromkeys(ids)):
        photo = photos[pk]
        created.append(
            ProductImage.objects.create(
                product=product,
                image=photo.image.name,
                alt_text=product.title,
                sort_order=start + n,
                source_photo=photo,
            )
        )
        photo.status, photo.reusable = LotPhoto.ASSIGNED, False
        photo.assigned_by, photo.assigned_at = user, now
        photo.save(update_fields=["status", "reusable", "assigned_by", "assigned_at"])
    return created


def _can_pick(photo):
    return photo.status == LotPhoto.UNASSIGNED or (
        photo.status == LotPhoto.ASSIGNED and photo.reusable
    )


@transaction.atomic
def remove_image(image, user):
    """Take a photo off an item. A tray photo goes back to the tray; other images go."""
    photo = image.source_photo
    image.delete()
    if photo is None:
        return
    photo = LotPhoto.objects.select_for_update().get(pk=photo.pk)
    if photo.status == LotPhoto.ASSIGNED and not photo.uses.exists():
        photo.status, photo.reusable = LotPhoto.UNASSIGNED, False
        photo.assigned_by, photo.assigned_at = None, None
        photo._change_reason = f"Taken off an item by {user}"
        photo.save()


def use_again(photo, user):
    if photo.status != LotPhoto.ASSIGNED:
        raise TrayError("Only an assigned photo can be used again.")
    photo.reusable = True
    photo._change_reason = f"Use again, by {user}"
    photo.save(update_fields=["reusable"])


def mark_not_usable(photo, user):
    if photo.status != LotPhoto.UNASSIGNED:
        raise TrayError("Take the photo off its item first.")
    photo.status = LotPhoto.NOT_USABLE
    photo._change_reason = f"Not usable, by {user or 'the demo seed'}"
    photo.save(update_fields=["status"])


def restore(photo, user):
    if photo.status != LotPhoto.NOT_USABLE:
        raise TrayError("This photo is not in the Not usable tab.")
    photo.status = LotPhoto.UNASSIGNED
    photo.save(update_fields=["status"])


@transaction.atomic
def delete_photo(photo, user):
    """Only the owner deletes, and only a photo in the Not usable tab."""
    if not user.is_superuser:
        raise PermissionDenied
    if photo.status != LotPhoto.NOT_USABLE or photo.uses.exists():
        raise TrayError('Move the photo to "Not usable" before you delete it.')
    for field in (photo.image, photo.thumbnail):
        if field:
            field.delete(save=False)
    photo.delete()


def counts(photos):
    """Counts by status, and unassigned photos older than OLD_AFTER_DAYS."""
    old = timezone.now() - datetime.timedelta(days=OLD_AFTER_DAYS)
    return photos.aggregate(
        total=Count("pk"),
        unassigned=Count("pk", filter=Q(status=LotPhoto.UNASSIGNED)),
        assigned=Count("pk", filter=Q(status=LotPhoto.ASSIGNED)),
        not_usable=Count("pk", filter=Q(status=LotPhoto.NOT_USABLE)),
        old=Count("pk", filter=Q(status=LotPhoto.UNASSIGNED, uploaded_at__lt=old)),
    )


def trays():
    """One row per lot with photos, plus the "No lot" tray: (lot or None, counts)."""
    rows = (
        LotPhoto.objects.values("lot")
        .annotate(
            total=Count("pk"),
            unassigned=Count("pk", filter=Q(status=LotPhoto.UNASSIGNED)),
            assigned=Count("pk", filter=Q(status=LotPhoto.ASSIGNED)),
            not_usable=Count("pk", filter=Q(status=LotPhoto.NOT_USABLE)),
        )
        .order_by()
    )
    return {row.pop("lot"): row for row in rows}
