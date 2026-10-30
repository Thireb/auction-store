from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render

from .models import Category, Product, ProductImage, Variant
from .pricing import buyer_is_wholesale, visible_tiers

PAGE_SIZE = 24


def product_queryset(listed=True):
    products = Product.objects.listed() if listed else Product.objects.visible()
    return products.select_related("category", "brand").prefetch_related(
        Prefetch(
            "variants",
            queryset=Variant.objects.filter(is_active=True).prefetch_related("price_tiers"),
        ),
        Prefetch("images", queryset=ProductImage.objects.order_by("sort_order", "pk")),
    )


def _render_list(request, products, context):
    page = Paginator(products, PAGE_SIZE).get_page(request.GET.get("page"))
    context.update({"page_obj": page, "products": page.object_list})
    return render(request, "catalog/product_list.html", context)


def product_list(request):
    return _render_list(request, product_queryset(), {"title": "All products"})


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    products = product_queryset().filter(category_id__in=category.descendant_ids())
    context = {
        "title": category.name,
        "category": category,
        "breadcrumbs": category.ancestors(),
        "subcategories": category.children.filter(is_active=True),
    }
    return _render_list(request, products, context)


def product_detail(request, slug):
    product = get_object_or_404(product_queryset(listed=False), slug=slug)
    variants = product.active_variants()
    wholesale = buyer_is_wholesale(request.user)
    context = {
        "product": product,
        "variants": variants,
        "variant_data": [
            {
                "id": v.pk,
                "name": v.name,
                "price": int(v.price),
                "compare": int(v.compare_at_price) if v.compare_at_price else None,
                "min_qty": v.min_order_qty,
                "step": v.order_step,
                "in_stock": v.in_stock,
                "available": v.stock_available if v.track_stock else None,
                "tiers": [
                    {
                        "min": t.min_quantity,
                        "price": int(t.unit_price),
                        "wholesale": t.wholesale_only,
                    }
                    for t in visible_tiers(v, wholesale)
                ],
            }
            for v in variants
        ],
        "images": list(product.images.all()),
        "attributes": product.attribute_values(),
        "breadcrumbs": product.category.ancestors(include_self=True),
    }
    return render(request, "catalog/product_detail.html", context)
