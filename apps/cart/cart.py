"""A session cart. It stores only variant ids and quantities; prices are always calculated."""

from dataclasses import dataclass
from decimal import Decimal

from apps.catalog import pricing
from apps.catalog.models import Variant

SESSION_KEY = "cart"


@dataclass
class CartLine:
    variant: Variant
    quantity: int
    unit_price: Decimal
    error: str | None

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def product(self):
        return self.variant.product

    @property
    def regular_total(self):
        return self.variant.price * self.quantity

    @property
    def saving(self):
        return self.regular_total - self.line_total


class Cart:
    def __init__(self, request):
        self.session = request.session
        self.wholesale = pricing.buyer_is_wholesale(getattr(request, "user", None))
        self.items = {str(k): int(v) for k, v in self.session.get(SESSION_KEY, {}).items()}
        self._lines = None

    def _save(self):
        self.session[SESSION_KEY] = self.items
        self.session.modified = True
        self._lines = None

    def set(self, variant, quantity):
        if quantity <= 0:
            self.items.pop(str(variant.pk), None)
        else:
            self.items[str(variant.pk)] = quantity
        self._save()

    def add(self, variant, quantity):
        self.set(variant, self.items.get(str(variant.pk), 0) + quantity)

    def remove(self, variant_id):
        self.items.pop(str(variant_id), None)
        self._save()

    def clear(self):
        self.items = {}
        self._save()

    def quantity_of(self, variant):
        return self.items.get(str(variant.pk), 0)

    @property
    def count(self):
        return sum(self.items.values())

    def __len__(self):
        return len(self.items)

    @property
    def lines(self):
        if self._lines is None:
            variants = (
                Variant.objects.filter(pk__in=self.items, is_active=True, product__is_active=True)
                .select_related("product__category")
                .prefetch_related("price_tiers", "product__images")
            )
            found = {str(v.pk): v for v in variants}
            # Drop items that no longer exist or were hidden.
            for key in [k for k in self.items if k not in found]:
                self.items.pop(key)
                self._save()
            self._lines = [
                CartLine(
                    variant=v,
                    quantity=self.items[key],
                    unit_price=pricing.unit_price(v, self.items[key], self.wholesale),
                    error=pricing.quantity_error(v, self.items[key]),
                )
                for key, v in found.items()
            ]
            self._lines.sort(key=lambda line: line.variant.pk)
        return self._lines

    @property
    def subtotal(self):
        return sum((line.line_total for line in self.lines), Decimal(0))

    @property
    def savings(self):
        return sum((line.saving for line in self.lines), Decimal(0))

    @property
    def has_errors(self):
        return any(line.error for line in self.lines)

    @property
    def has_bulky(self):
        return any(line.product.bulky for line in self.lines)
