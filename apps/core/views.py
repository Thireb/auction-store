from django.conf import settings
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from apps.catalog.views import product_queryset

from .models import Page


def home(request):
    context = {
        "featured": product_queryset().filter(is_featured=True)[:8],
        "latest": product_queryset()[:8],
    }
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
        "Disallow: /cart/",
        "Disallow: /checkout/",
        "Disallow: /account/",
        "Disallow: /order/",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
