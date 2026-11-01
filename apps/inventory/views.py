"""Public lot pages in the store. Staff manage lots in the staff portal."""

import datetime

from django.conf import settings
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from apps.catalog.saved import Saved
from apps.catalog.views import product_queryset

from . import lots
from .models import Lot

PAGE_SIZE = 24
DIG_LIMIT = 80


def lot_list(request):
    context = {
        "upcoming": lots.upcoming_lots(),
        "open_lots": lots.open_lots(),
        "past": lots.past_lots(),
    }
    return render(request, "lots/lot_list.html", context)


def _public_lot(slug):
    lot = get_object_or_404(Lot.objects.public(), slug=slug)
    return lots.attach_counts([lot])[0]


def lot_detail(request, slug):
    lot = _public_lot(slug)
    context = {"lot": lot, "seconds": lots.seconds_until(lot.opens_at)}
    if lot.is_open:
        chip = request.GET.get("f") if request.GET.get("f") in lots.CHIPS else "all"
        products = lots.apply_chip(lots.lot_products(product_queryset(), lot), chip)
        page = Paginator(products.order_by("-created_at", "-pk"), PAGE_SIZE).get_page(
            request.GET.get("page")
        )
        context.update(
            {
                "page_obj": page,
                "products": page.object_list,
                "chips": lots.chip_list(chip),
                "chip": chip,
                "sold": lots.sold_in_lot(lot),
            }
        )
        if request.htmx and not request.htmx.boosted:
            return render(request, "lots/partials/lot_grid.html", context)
    return render(request, "lots/lot_detail.html", context)


def dig(request, slug):
    lot = _public_lot(slug)
    if not lot.is_open:
        raise Http404
    saved = Saved(request)
    products = list(lots.lot_products(product_queryset(), lot).order_by("?")[:DIG_LIMIT])
    items = []
    for p in products:
        image = p.main_image
        left = p.pieces_left
        items.append(
            {
                "id": p.pk,
                "title": p.title,
                "note": p.brand.name if p.brand else p.category.name,
                "price": f"{'From ' if len(p.active_variants()) > 1 else ''}Rs {p.min_price:,.0f}",
                "condition": p.condition_short,
                "left": "1 piece" if left == 1 else f"{left} left" if left else "",
                "image": image.image.url if image else "",
                "url": p.get_absolute_url(),
                "save_url": reverse("catalog:saved_toggle", args=[p.pk]),
                "saved": p in saved,
            }
        )
    context = {"lot": lot, "dig_data": {"items": items, "total": lot.items_left}}
    return render(request, "lots/dig.html", context)


def _ics_text(value):
    """Escape text for an iCalendar line."""
    for char, escaped in [("\\", "\\\\"), (",", "\\,"), (";", "\\;"), ("\n", "\\n")]:
        value = value.replace(char, escaped)
    return value


def calendar(request, slug):
    """A calendar event for the lot opening: a free reminder on the customer's phone."""
    lot = get_object_or_404(Lot.objects.public(), slug=slug, opens_at__isnull=False)
    start = lot.opens_at.astimezone(datetime.UTC)
    end = start + datetime.timedelta(minutes=30)
    stamp = timezone.now().astimezone(datetime.UTC)
    url = request.build_absolute_uri(lot.get_absolute_url())
    fmt = "%Y%m%dT%H%M%SZ"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{_ics_text(settings.STORE_NAME)}//Lots//EN",
        "BEGIN:VEVENT",
        f"UID:lot-{lot.pk}@{request.get_host()}",
        f"DTSTAMP:{stamp.strftime(fmt)}",
        f"DTSTART:{start.strftime(fmt)}",
        f"DTEND:{end.strftime(fmt)}",
        f"SUMMARY:{_ics_text(f'Lot {lot.reference} opens at {settings.STORE_NAME}')}",
        f"DESCRIPTION:{_ics_text(lot.title)}\\n{_ics_text(url)}",
        f"URL:{url}",
        "BEGIN:VALARM",
        "TRIGGER:-PT15M",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_ics_text(f'Lot {lot.reference} opens in 15 minutes')}",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    response = HttpResponse("\r\n".join(lines) + "\r\n", content_type="text/calendar")
    response["Content-Disposition"] = f'attachment; filename="lot-{lot.slug}.ics"'
    return response
