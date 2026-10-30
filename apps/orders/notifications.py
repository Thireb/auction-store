"""Messages about orders. Only free channels: email by SMTP, and WhatsApp click-to-chat links.

A paid WhatsApp or SMS service can be added later in these functions without other changes.
"""

import logging
from urllib.parse import quote

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)


def whatsapp_url(phone, text):
    """A wa.me link that opens WhatsApp with `text` ready to send to `phone` (+92...)."""
    return f"https://wa.me/{phone.lstrip('+')}?text={quote(text)}"


def confirmation_message(order):
    return (
        f"Assalam o Alaikum {order.full_name}, this is {settings.STORE_NAME}. "
        f"We received your order {order.number} for Rs {order.total:,} (Cash on Delivery) "
        f"to {order.city_name}. Please reply YES to confirm."
    )


def order_whatsapp_url(order):
    return whatsapp_url(order.phone, confirmation_message(order))


def order_placed(order, request=None):
    """Email the owner about a new order, if ORDER_ALERT_EMAIL is set."""
    if not settings.ORDER_ALERT_EMAIL:
        return
    path = reverse("admin:orders_order_change", args=[order.pk])
    link = request.build_absolute_uri(path) if request else path
    lines = [
        f"{item.quantity} x {item.product_title} {item.variant_name}" for item in order.items.all()
    ]
    body = "\n".join(
        [
            f"New order {order.number}",
            f"{order.full_name}, {order.phone_display}, {order.city_name}",
            f"Total: Rs {order.total:,}",
            "",
            *lines,
            "",
            link,
        ]
    )
    try:
        send_mail(
            f"New order {order.number} - Rs {order.total:,}",
            body,
            settings.DEFAULT_FROM_EMAIL,
            [settings.ORDER_ALERT_EMAIL],
        )
    except Exception:  # A mail problem must never stop an order.
        logger.exception("Could not send the new order email for %s", order.number)
