"""Starter content pages. The owner edits them in the admin."""

from .models import Page

PAGES = [
    (
        "About us",
        "We sell items from Dubai auctions and export leftovers at fair prices.\n\n"
        "Every item is checked by our team before it is listed.",
    ),
    (
        "Delivery information",
        "We deliver across Pakistan. Payment is Cash on Delivery.\n\n"
        "We call you to confirm every order before we send it. "
        "Large items such as furniture need an advance payment.",
    ),
    (
        "FAQ",
        "How do I pay?\nCash on Delivery. You pay the courier when the parcel arrives.\n\n"
        "Can I buy in bulk?\nYes. Bulk prices show on the product page. "
        "Shops can apply for wholesale prices from their account.",
    ),
    ("Contact us", "Phone and WhatsApp: 0300 0000000\nEmail: store@example.com"),
]


def seed_pages(stdout=None):
    for order, (title, body) in enumerate(PAGES):
        Page.objects.get_or_create(title=title, defaults={"body": body, "sort_order": order})
    if stdout:
        stdout.write("Pages: starter pages ready.")
