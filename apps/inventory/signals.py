from django.dispatch import Signal

# Sent after every stock change, with the locked `variant`. Catalog uses it for "sold out".
stock_changed = Signal()
