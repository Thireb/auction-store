from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from apps.catalog.views import product_queryset


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
