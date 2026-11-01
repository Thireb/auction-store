"""Saved pieces and recently viewed products.

Guests save in the session. A signed-in customer saves in SavedProduct, so the list is the
same on every phone. At login the session list moves into the account (merge_on_login).
"""

from .models import Product, SavedProduct

SESSION_KEY = "saved_products"
RECENT_KEY = "recent_products"
RECENT_LIMIT = 12


class Saved:
    def __init__(self, request):
        self.session = request.session
        user = getattr(request, "user", None)
        self.user = user if user is not None and user.is_authenticated else None
        self._ids = None

    @property
    def ids(self):
        if self._ids is None:
            if self.user:
                rows = SavedProduct.objects.filter(user=self.user).values_list("product_id")
                self._ids = [pk for (pk,) in rows]
            else:
                self._ids = [int(pk) for pk in self.session.get(SESSION_KEY, [])]
        return self._ids

    def __contains__(self, product):
        return getattr(product, "pk", product) in self.ids

    def __len__(self):
        return len(self.ids)

    def toggle(self, product):
        """Save or unsave `product`. Return True if it is saved now."""
        saved = product.pk not in self.ids
        if self.user:
            if saved:
                SavedProduct.objects.get_or_create(user=self.user, product=product)
            else:
                SavedProduct.objects.filter(user=self.user, product=product).delete()
        else:
            ids = [pk for pk in self.ids if pk != product.pk]
            self.session[SESSION_KEY] = [product.pk, *ids] if saved else ids
        self._ids = None
        return saved

    def products(self):
        """Saved products a customer can still open or see as sold, newest saved first."""
        order = {pk: i for i, pk in enumerate(self.ids)}
        products = Product.objects.visible().filter(pk__in=order)
        return sorted(products, key=lambda p: order[p.pk])


def merge_on_login(sender, request, user, **kwargs):
    """Move the guest's saved pieces into the account. Connected to user_logged_in."""
    ids = request.session.pop(SESSION_KEY, []) if hasattr(request, "session") else []
    existing = set(SavedProduct.objects.filter(user=user).values_list("product_id", flat=True))
    valid = Product.objects.filter(pk__in=ids).values_list("pk", flat=True)
    SavedProduct.objects.bulk_create(
        [SavedProduct(user=user, product_id=pk) for pk in valid if pk not in existing]
    )


def remember_viewed(request, product):
    ids = [pk for pk in request.session.get(RECENT_KEY, []) if pk != product.pk]
    request.session[RECENT_KEY] = [product.pk, *ids][:RECENT_LIMIT]


def recent_ids(request, exclude=None):
    return [pk for pk in request.session.get(RECENT_KEY, []) if pk != exclude]
