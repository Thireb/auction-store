from dataclasses import dataclass
from decimal import Decimal

from .models import ShippingSettings


@dataclass
class FeeQuote:
    delivery_fee: Decimal
    cod_fee: Decimal

    @property
    def total(self):
        return self.delivery_fee + self.cod_fee


def quote(city, subtotal, has_bulky=False, settings=None):
    """Delivery and COD fees for an order to `city`. All amounts come from the admin."""
    settings = settings or ShippingSettings.load()
    delivery = city.delivery_fee if city.delivery_fee is not None else settings.default_delivery_fee
    if settings.free_delivery_above is not None and subtotal >= settings.free_delivery_above:
        delivery = Decimal(0)
    if has_bulky:
        delivery += settings.bulky_item_fee
    cod = city.cod_fee if city.cod_fee is not None else settings.default_cod_fee
    return FeeQuote(delivery_fee=Decimal(delivery), cod_fee=Decimal(cod))
