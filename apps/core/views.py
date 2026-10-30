from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache


def home(request):
    return render(request, "core/home.html")


@never_cache
def healthz(request):
    """Used by Docker and PetHost to check that the app and the database work."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})
