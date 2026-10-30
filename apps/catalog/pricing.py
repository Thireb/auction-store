"""Prices and order quantity rules. The cart and checkout use only these functions."""


def buyer_is_wholesale(user):
    """True for a signed-in buyer whose wholesale application is approved."""
    profile = getattr(user, "wholesale_profile", None) if user else None
    return bool(profile and profile.is_approved)


def visible_tiers(variant, wholesale=False):
    """Tiers that this buyer can get, lowest quantity first."""
    tiers = list(variant.price_tiers.all())
    if not wholesale:
        tiers = [t for t in tiers if not t.wholesale_only]
    return sorted(tiers, key=lambda t: (t.min_quantity, t.unit_price))


def unit_price(variant, quantity, wholesale=False):
    """The lowest price the buyer gets for this quantity."""
    prices = [variant.price]
    prices += [
        t.unit_price for t in visible_tiers(variant, wholesale) if quantity >= t.min_quantity
    ]
    return min(prices)


def line_total(variant, quantity, wholesale=False):
    return unit_price(variant, quantity, wholesale) * quantity


def quantity_error(variant, quantity):
    """A message if the quantity breaks the minimum or the step rule, else None."""
    if quantity < 1:
        return "Quantity must be at least 1."
    if quantity < variant.min_order_qty:
        return f"The minimum order for this item is {variant.min_order_qty}."
    if (quantity - variant.min_order_qty) % variant.order_step:
        return f"This item is sold in steps of {variant.order_step} from {variant.min_order_qty}."
    if variant.track_stock and quantity > variant.stock_available:
        available = max(variant.stock_available, 0)
        return f"Only {available} available." if available else "This item is sold out."
    return None


def nearest_valid_quantity(variant, quantity):
    """Round a quantity to the closest allowed value at or above the minimum."""
    quantity = max(quantity, variant.min_order_qty)
    extra = (quantity - variant.min_order_qty) % variant.order_step
    return quantity - extra if extra else quantity
