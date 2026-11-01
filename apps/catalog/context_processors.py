from django.utils.functional import SimpleLazyObject

from .saved import Saved


def storefront(request):
    """Saved pieces for hearts and the header badge. Loaded only if a template uses them."""
    if not hasattr(request, "session"):
        return {}
    saved = SimpleLazyObject(lambda: Saved(request))
    return {"saved": saved, "saved_count": lambda: len(saved)}
