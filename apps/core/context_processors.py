from django.conf import settings

from .models import Page


def store(request):
    return {
        "STORE_NAME": settings.STORE_NAME,
        "footer_pages": Page.objects.filter(is_active=True, show_in_footer=True).only(
            "title", "slug"
        ),
    }
