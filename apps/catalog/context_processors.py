from .models import Category


def nav_categories(request):
    """Top-level categories for the site menu. Lazy, so pages that do not show it pay nothing."""
    return {
        "nav_categories": Category.objects.filter(parent__isnull=True, is_active=True).only(
            "name", "slug"
        )
    }
