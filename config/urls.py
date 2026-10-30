from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core import dashboard

admin.site.site_header = f"{settings.STORE_NAME} admin"
admin.site.site_title = settings.STORE_NAME
admin.site.index_title = "Back office"

urlpatterns = [
    path(settings.ADMIN_URL, include(dashboard.urlpatterns)),
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("apps.core.urls")),
    path("", include("apps.catalog.urls")),
    path("cart/", include("apps.cart.urls")),
    path("", include("apps.orders.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
