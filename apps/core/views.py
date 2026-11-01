from django.conf import settings
from django.db import connection
from django.db.models import Count, Prefetch
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from apps.catalog.models import Category, Product, ProductImage, Variant
from apps.catalog.views import product_queryset
from apps.inventory import lots
from apps.shipping.models import ShippingSettings

from .models import Page

# The hero fans out these many pieces of the current lot.
FAN_SIZE = 5
FAN_LAYOUT = [  # x offset, y offset, rotation, delay, z-index; the middle card is on top.
    ("-190px", "40px", "-14deg", ".35s", 1),
    ("190px", "40px", "14deg", ".45s", 1),
    ("-95px", "10px", "-6deg", ".55s", 2),
    ("95px", "10px", "6deg", ".65s", 2),
    ("0px", "0px", "0deg", ".75s", 3),
]


def category_tiles():
    """Top-level categories with the number of listed products in them and below. 2 queries."""
    counts = dict(
        Product.objects.listed().values_list("category").annotate(n=Count("pk")).order_by()
    )
    categories = list(Category.objects.filter(is_active=True).only("name", "slug", "parent"))
    by_id = {c.pk: c for c in categories}
    roots = {c.pk: c for c in categories if c.parent_id is None}
    for root in roots.values():
        root.listed_count = 0
    for category_id, n in counts.items():
        node = by_id.get(category_id)
        while node is not None and node.parent_id is not None:
            node = by_id.get(node.parent_id)
        if node is not None and node.pk in roots:
            node.listed_count += n
    return [c for c in roots.values() if c.listed_count][:8]


def sold_products(limit=5):
    return Product.objects.recently_sold().prefetch_related(
        Prefetch("variants", queryset=Variant.objects.filter(is_active=True)),
        Prefetch("images", queryset=ProductImage.objects.order_by("sort_order", "pk")),
    )[:limit]


def home(request):
    lot = lots.current_lot()
    upcoming = lots.next_lot()
    context = {
        "lot": lot,
        "next_lot": upcoming,
        "next_seconds": lots.seconds_until(upcoming.opens_at) if upcoming else 0,
        "tiles": category_tiles(),
        "sold": sold_products(),
        "whatsapp_url": ShippingSettings.load().whatsapp_channel_url,
        "featured": product_queryset().filter(is_featured=True)[:8],
    }
    if lot:
        in_lot = lots.lot_products(product_queryset(), lot).order_by("-is_featured", "-created_at")
        fan = list(in_lot.filter(images__isnull=False).distinct()[:FAN_SIZE])
        layout = FAN_LAYOUT[-len(fan) :] if fan else []
        context.update(
            {
                "fan": [(p, *place) for p, place in zip(fan, layout, strict=True)],
                "products": in_lot[:8],
                "chips": lots.chip_list("all"),
            }
        )
    else:
        context["latest"] = product_queryset()[:8]
    return render(request, "core/home.html", context)


@never_cache
def healthz(request):
    """Used by Docker and PetHost to check that the app and the database work."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


def page(request, slug):
    return render(
        request, "core/page.html", {"page": get_object_or_404(Page, slug=slug, is_active=True)}
    )


def robots_txt(request):
    lines = [
        "User-agent: *",
        f"Disallow: /{settings.ADMIN_URL}",
        "Disallow: /staff/",
        "Disallow: /cart/",
        "Disallow: /checkout/",
        "Disallow: /account/",
        "Disallow: /order/",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
