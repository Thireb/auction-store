from django.contrib.auth.views import LogoutView
from django.urls import path, reverse_lazy

from .views import catalog, orders, owner, photos
from .views.simple import CRUDS

app_name = "portal"

urlpatterns = [
    path("", owner.dashboard, name="dashboard"),
    path("login/", owner.PortalLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page=reverse_lazy("portal:login")), name="logout"),
    # Orders
    path("orders/", orders.order_list, name="order_list"),
    path("orders/<int:pk>/", orders.order_detail, name="order_detail"),
    path(
        "orders/<int:pk>/status/<str:target>/",
        orders.order_transition,
        name="order_transition",
    ),
    path("orders/<int:pk>/advance/", orders.order_advance, name="order_advance"),
    path("orders/<int:pk>/print/", orders.order_print, name="order_print"),
    path("wholesale/", orders.wholesale_list, name="wholesale_list"),
    path(
        "wholesale/<int:pk>/<str:status>/",
        orders.wholesale_review,
        name="wholesale_review",
    ),
    # Catalog and stock
    path("products/", catalog.product_list, name="product_list"),
    path("products/new/", catalog.product_edit, name="product_add"),
    path("products/<int:pk>/", catalog.product_edit, name="product_edit"),
    path("products/<int:pk>/delete/", catalog.product_delete, name="product_delete"),
    path("products/attributes/", catalog.product_attributes, name="product_attributes"),
    path("variants/<int:pk>/", catalog.variant_detail, name="variant_detail"),
    path("stock/", catalog.stock_list, name="stock_list"),
    path("stock/near-empty/", catalog.stock_list, {"level": "low"}, name="stock_near_empty"),
    path("stock/out/", catalog.stock_list, {"level": "out"}, name="stock_out"),
    path("stock/movements/", catalog.movement_list, name="movement_list"),
    path("stock/import/", catalog.import_view, name="import_csv"),
    path("photos/", photos.tray_list, name="tray_list"),
    path("photos/<str:key>/", photos.tray_detail, name="tray_detail"),
    path("photos/<str:key>/upload/", photos.tray_upload, name="tray_upload"),
    path("photos/item/<int:pk>/<str:action>/", photos.photo_action, name="photo_action"),
    path("products/<int:pk>/photos/", photos.pick_photos, name="pick_photos"),
    # Owner
    path("settings/", owner.settings_view, name="settings"),
    path("staff/", owner.staff_list, name="staff_list"),
    path("staff/new/", owner.staff_edit, name="staff_add"),
    path("staff/<int:pk>/", owner.staff_edit, name="staff_edit"),
    path("activity/", owner.activity_view, name="activity"),
]

for prefix, crud in CRUDS.items():
    urlpatterns += crud.urls(prefix)
