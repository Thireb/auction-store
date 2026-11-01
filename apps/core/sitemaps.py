from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.catalog.models import Category, Product
from apps.inventory.models import Lot

from .models import Page


class StaticSitemap(Sitemap):
    def items(self):
        return ["core:home", "lots:list", "catalog:product_list"]

    def location(self, item):
        return reverse(item)


class CategorySitemap(Sitemap):
    def items(self):
        return Category.objects.filter(is_active=True)


class ProductSitemap(Sitemap):
    limit = 5000

    def items(self):
        return Product.objects.listed().order_by("-updated_at")

    def lastmod(self, obj):
        return obj.updated_at


class LotSitemap(Sitemap):
    def items(self):
        return Lot.objects.public().order_by("-pk")


class PageSitemap(Sitemap):
    def items(self):
        return Page.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {
    "static": StaticSitemap,
    "lots": LotSitemap,
    "categories": CategorySitemap,
    "products": ProductSitemap,
    "pages": PageSitemap,
}
