import pytest
from django.urls import reverse

from apps.catalog.tests.factories import ProductFactory, VariantFactory
from apps.core.models import Page

pytestmark = pytest.mark.django_db


def test_page_and_footer_link(client):
    page = Page.objects.create(title="Delivery information", body="We deliver.\n\nCOD only.")
    Page.objects.create(title="Hidden", body="x", is_active=False)
    response = client.get(page.get_absolute_url())
    content = response.content.decode()
    assert "<p>COD only.</p>" in content
    assert f'href="{page.get_absolute_url()}"' in content
    assert client.get(reverse("core:page", args=["hidden"])).status_code == 404


def test_sitemap_lists_products_and_pages(client):
    product = ProductFactory(title="Brass lamp")
    VariantFactory(track_stock=False, product=product)
    Page.objects.create(title="FAQ", body="x")
    content = client.get(reverse("sitemap")).content.decode()
    assert product.get_absolute_url() in content
    assert "/pages/faq/" in content


def test_robots_txt(client):
    content = client.get(reverse("robots_txt")).content.decode()
    assert "Disallow: /checkout/" in content
    assert "Sitemap: http://testserver/sitemap.xml" in content


def test_product_page_has_open_graph_tags(client):
    variant = VariantFactory(track_stock=False, product=ProductFactory(title="Brass lamp"))
    content = client.get(variant.product.get_absolute_url()).content.decode()
    assert '<meta property="og:title" content="Brass lamp">' in content
    assert 'rel="canonical"' in content
