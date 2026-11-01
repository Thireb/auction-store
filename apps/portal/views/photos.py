"""Lot photo trays in the staff portal: upload many photos, then pick them for items."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.catalog.models import Product, ProductImage
from apps.inventory import photos
from apps.inventory.models import Lot, LotPhoto, StockItem

from ..access import portal_view

PAGE_SIZE = 120
NO_LOT = "none"
TABS = [
    (LotPhoto.UNASSIGNED, "Unassigned"),
    (LotPhoto.ASSIGNED, "Assigned"),
    (LotPhoto.NOT_USABLE, "Not usable"),
]


def _tray_lot(key):
    """The lot for a tray key in a URL. "none" is the "No lot" tray."""
    if key == NO_LOT:
        return None
    if not str(key).isdigit():
        raise Http404
    return get_object_or_404(Lot, pk=key)


def _tray_key(lot):
    return str(lot.pk) if lot else NO_LOT


@portal_view("inventory.view_lotphoto")
def tray_list(request):
    counts = photos.trays()
    lots = list(Lot.objects.all()[:200])
    rows = [(None, NO_LOT, counts.get(None, {}))]
    rows += [(lot, str(lot.pk), counts.get(lot.pk, {})) for lot in lots]
    context = {
        "title": "Photo trays",
        "rows": rows,
        "old": photos.counts(LotPhoto.objects.all())["old"],
        "old_days": photos.OLD_AFTER_DAYS,
    }
    return render(request, "portal/photos/tray_list.html", context)


def _items_without_photos(lot):
    """Products of this lot that have no photo yet, so staff know what is left."""
    stock = StockItem.objects.filter(lot=lot) if lot else StockItem.objects.filter(lot=None)
    has_image = ProductImage.objects.filter(product=OuterRef("pk"))
    return (
        Product.objects.filter(pk__in=stock.values("variant__product"))
        .exclude(Exists(has_image))
        .order_by("title")[:100]
    )


@portal_view("inventory.view_lotphoto")
def tray_detail(request, key):
    lot = _tray_lot(key)
    tab = request.GET.get("tab") if request.GET.get("tab") in dict(TABS) else LotPhoto.UNASSIGNED
    in_tray = LotPhoto.objects.in_tray(lot)
    page = Paginator(
        in_tray.filter(status=tab)
        .select_related("uploaded_by", "assigned_by")
        .prefetch_related("uses__product"),
        PAGE_SIZE,
    ).get_page(request.GET.get("page"))
    context = {
        "title": f"Photos of lot {lot}" if lot else "Photos with no lot",
        "lot": lot,
        "key": key,
        "tab": tab,
        "tabs": TABS,
        "page_obj": page,
        "counts": photos.counts(in_tray),
        "old_days": photos.OLD_AFTER_DAYS,
        "missing": _items_without_photos(lot),
        "can_upload": request.user.has_perm("inventory.add_lotphoto"),
        "can_change": request.user.has_perm("inventory.change_lotphoto"),
    }
    return render(request, "portal/photos/tray_detail.html", context)


@require_POST
@portal_view("inventory.add_lotphoto")
def tray_upload(request, key):
    """One photo per request, so a slow phone network can retry a single photo."""
    lot = _tray_lot(key)
    upload = request.FILES.get("photo")
    if upload is None:
        return JsonResponse({"error": "Choose a photo."}, status=400)
    try:
        photo = photos.add_photo(lot, upload, request.user)
    except ValidationError as exc:
        return JsonResponse({"error": exc.messages[0]}, status=400)
    return JsonResponse({"id": photo.pk, "thumb": photo.thumb_url})


ACTIONS = {
    "use_again": photos.use_again,
    "not_usable": photos.mark_not_usable,
    "restore": photos.restore,
}


@require_POST
@portal_view("inventory.change_lotphoto")
def photo_action(request, pk, action):
    photo = get_object_or_404(LotPhoto, pk=pk)
    back = reverse("portal:tray_detail", args=[_tray_key(photo.lot)])
    try:
        if action == "delete":
            photos.delete_photo(photo, request.user)
            messages.success(request, "Photo deleted.")
        elif action in ACTIONS:
            ACTIONS[action](photo, request.user)
        else:
            raise Http404
    except photos.TrayError as exc:
        messages.error(request, str(exc))
    return redirect(f"{back}?tab={request.POST.get('tab', LotPhoto.UNASSIGNED)}")


@portal_view(["catalog.change_product", "catalog.add_productimage", "inventory.view_lotphoto"])
def pick_photos(request, pk):
    """A full page to tap photos from a tray and put them on one item."""
    product = get_object_or_404(Product, pk=pk)
    product_lots = list(
        Lot.objects.filter(stock_items__variant__product=product).distinct().order_by("-pk")
    )
    counts = photos.trays()
    trays = [(lot, str(lot.pk), counts.get(lot.pk, {})) for lot in product_lots]
    trays += [
        (lot, str(lot.pk), counts[lot.pk])
        for lot in Lot.objects.filter(pk__in=[k for k in counts if k]).exclude(
            pk__in=[lot.pk for lot in product_lots]
        )
    ]
    trays.append((None, NO_LOT, counts.get(None, {})))
    key = request.GET.get("tray") or (trays[0][1] if trays else NO_LOT)
    lot = _tray_lot(key)

    if request.method == "POST":
        picked = [pk for pk in request.POST.getlist("photo") if pk.isdigit()]
        try:
            if not picked:
                raise photos.TrayError("Tap at least 1 photo.")
            added = photos.assign(picked, product, request.user)
        except photos.TrayError as exc:
            messages.error(request, str(exc))
            return redirect(f"{request.path}?tray={key}")
        messages.success(request, f"Added {len(added)} photo{'s' if len(added) != 1 else ''}.")
        return redirect(reverse("portal:product_edit", args=[product.pk]) + "#photos")

    context = {
        "title": f"Pick photos for {product}",
        "product": product,
        "trays": trays,
        "key": key,
        "lot": lot,
        "choices": LotPhoto.objects.in_tray(lot).pickable().prefetch_related("uses__product")[:400],
        "current": product.images.all(),
    }
    return render(request, "portal/photos/pick.html", context)
