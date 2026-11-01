from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"
    label = "catalog"

    def ready(self):
        from django.contrib.auth.signals import user_logged_in

        from apps.inventory.signals import stock_changed

        from .receivers import update_sold_out
        from .saved import merge_on_login

        stock_changed.connect(update_sold_out, dispatch_uid="catalog_update_sold_out")
        user_logged_in.connect(merge_on_login, dispatch_uid="catalog_merge_saved")
