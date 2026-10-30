from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.accounts import views as accounts_views
from apps.core import views as core_views
from apps.core.sitemaps import SITEMAPS

admin.site.site_header = f"{settings.STORE_NAME} admin"
admin.site.site_title = settings.STORE_NAME
admin.site.index_title = "Back office (owner fallback)"
# Staff work in the staff portal (/staff/). The Django admin stays as a hidden fallback
# for the owner only.
admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser

urlpatterns = [
    path("staff/", include("apps.portal.urls")),
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("apps.core.urls")),
    path("", include("apps.catalog.urls")),
    path("cart/", include("apps.cart.urls")),
    path("account/", include("apps.accounts.urls")),
    path("track/", accounts_views.track_order, name="track_order"),
    path("robots.txt", core_views.robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("", include("apps.orders.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
