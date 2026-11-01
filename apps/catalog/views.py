from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.inventory import lots
from apps.shipping.models import City

from . import nav
from .models import Category, Product, ProductImage, Variant
from .pricing import buyer_is_wholesale, visible_tiers
from .saved import Saved, recent_ids, remember_viewed
from .search import filter_options, filter_products

PAGE_SIZE = 24


def product_queryset():
    return (
        Product.objects.listed()
        .select_related("category", "brand")
        .prefetch_related(
            Prefetch(
                "variants",
                queryset=Variant.objects.filter(is_active=True).prefetch_related("price_tiers"),
            ),
            Prefetch("images", queryset=ProductImage.objects.order_by("sort_order", "pk")),
        )
    )


def ordered(products, ids):
    """`products` limited to `ids`, in the order of `ids`."""
    found = {p.pk: p for p in products.filter(pk__in=ids)}
    return [found[pk] for pk in ids if pk in found]


def _render_list(request, products, context, category=None):
    options = filter_options(products, category, request.GET)
    products, active = filter_products(products, request.GET, category)
    page = Paginator(products, PAGE_SIZE).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    context.update(
        {
            "page_obj": page,
            "products": page.object_list,
            "options": options,
            "active": active,
            "query_string": query.urlencode(),
        }
    )
    if request.htmx and not request.htmx.boosted:
        return render(request, "catalog/partials/results.html", context)
    return render(request, "catalog/product_list.html", context)


def product_list(request):
    title = "Search results" if request.GET.get("q") else "All products"
    return _render_list(request, product_queryset(), {"title": title})


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    products = product_queryset().filter(category_id__in=category.descendant_ids())
    context = {
        "title": category.name,
        "category": category,
        "breadcrumbs": category.ancestors(),
        "subcategories": category.children.filter(is_active=True),
    }
    return _render_list(request, products, context, category)


def product_detail(request, slug):
    product = get_object_or_404(product_queryset(), slug=slug)
    variants = product.active_variants()
    wholesale = buyer_is_wholesale(request.user)
    remember_viewed(request, product)
    lot = lots.lot_for_product(product)
    more = (
        lots.lot_products(product_queryset(), lot)
        if lot
        else product_queryset().filter(category=product.category)
    )
    parent = product.category.parent
    nearby = (parent.children if parent else Category.objects.filter(parent=None)).filter(
        is_active=True
    )
    context = {
        "product": product,
        "lot": lot,
        "more": more.exclude(pk=product.pk)[:8],
        "recent": ordered(product_queryset(), recent_ids(request, exclude=product.pk)[:8]),
        "nearby": nearby.exclude(pk=product.category_id)[:12],
        "cities": City.objects.filter(is_active=True, cod_allowed=True),
        "condition_steps": [
            (label, i <= _condition_index(product), key == product.condition)
            for i, (key, label) in enumerate(Product.CONDITION_SHORT.items())
        ],
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


def _condition_index(product):
    return list(Product.CONDITION_SHORT).index(product.condition)


def saved_list(request):
    saved = Saved(request)
    products = saved.products()
    listed_ids = set(
        product_queryset().filter(pk__in=[p.pk for p in products]).values_list("pk", flat=True)
    )
    context = {
        "available": ordered(product_queryset(), [p.pk for p in products if p.pk in listed_ids]),
        "gone": [p for p in products if p.pk not in listed_ids],
    }
    return render(request, "catalog/saved.html", context)


@require_POST
def saved_toggle(request, pk):
    product = get_object_or_404(Product.objects.visible(), pk=pk)
    saved = Saved(request)
    now_saved = saved.toggle(product)
    if request.htmx:
        context = {
            "product": product,
            "is_saved": now_saved,
            "just_saved": now_saved,
            "inline": request.POST.get("inline"),
            "count": len(saved),
        }
        return render(request, "catalog/partials/heart_result.html", context)
    target = request.POST.get("next")
    if not url_has_allowed_host_and_scheme(target, {request.get_host()}):
        target = product.get_absolute_url()
    return redirect(target)


def nav_children(request, pk):
    """HTMX: the sub-categories of one category, for the sidebar tree."""
    return render(request, "catalog/partials/category_tree.html", {"nodes": nav.children_of(pk)})


def nav_search(request):
    """HTMX: categories whose name matches the sidebar search box."""
    query = request.GET.get("q", "").strip()
    context = {"results": nav.search(query), "query": query}
    return render(request, "catalog/partials/category_search.html", context)
