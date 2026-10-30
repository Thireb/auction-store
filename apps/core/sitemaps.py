from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.catalog.models import Category, Product

from .models import Page


class StaticSitemap(Sitemap):
    def items(self):
        return ["core:home", "catalog:product_list"]

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


class PageSitemap(Sitemap):
    def items(self):
        return Page.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {
    "static": StaticSitemap,
    "categories": CategorySitemap,
    "products": ProductSitemap,
    "pages": PageSitemap,
}
