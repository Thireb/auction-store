from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"
    label = "catalog"

    def ready(self):
        from apps.inventory.signals import stock_changed

        from .receivers import update_sold_out

        stock_changed.connect(update_sold_out, dispatch_uid="catalog_update_sold_out")
