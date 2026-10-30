"""Search, filters and sorting for product lists. All values come from the query string."""

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Exists, F, Min, OuterRef, Q

from .models import Brand, Product, ProductAttributeValue, Variant

SORTS = {
    "newest": ("-created_at", "Newest"),
    "price_asc": ("min_price_value", "Price: low to high"),
    "price_desc": ("-min_price_value", "Price: high to low"),
}


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def filter_products(products, params, category=None):
    """Apply the query string to `products`. Return (queryset, active filter values)."""
    active = {}
    products = products.annotate(
        min_price_value=Min("variants__price", filter=Q(variants__is_active=True))
    )

    q = (params.get("q") or "").strip()[:100]
    if q:
        active["q"] = q
        vector = (
            SearchVector("title", weight="A")
            + SearchVector("brand__name", weight="B")
            + SearchVector("category__name", weight="B")
            + SearchVector("description", weight="C")
        )
        query = SearchQuery(q, search_type="websearch")
        # Match with the @@ operator: ts_rank gives 1e-20, not 0, to rows that do not match.
        products = products.annotate(search=vector, rank=SearchRank(vector, query)).filter(
            Q(search=query) | Q(title__icontains=q) | Q(variants__sku__iexact=q)
        )

    low, high = _int(params.get("min_price")), _int(params.get("max_price"))
    if low is not None:
        products = products.filter(min_price_value__gte=low)
        active["min_price"] = low
    if high is not None:
        products = products.filter(min_price_value__lte=high)
        active["max_price"] = high

    conditions = [c for c in params.getlist("condition") if c in dict(Product.CONDITION_CHOICES)]
    if conditions:
        products = products.filter(condition__in=conditions)
        active["condition"] = conditions

    brands = params.getlist("brand")
    if brands:
        products = products.filter(brand__slug__in=brands)
        active["brand"] = brands

    if params.get("in_stock"):
        available = Variant.objects.filter(product=OuterRef("pk"), is_active=True).filter(
            Q(track_stock=False) | Q(stock_on_hand__gt=F("stock_reserved"))
        )
        products = products.filter(Exists(available))
        active["in_stock"] = True

    if category is not None:
        for attribute in filterable_attributes(category):
            values = params.getlist(f"attr_{attribute.slug}")
            if values:
                match = ProductAttributeValue.objects.filter(
                    product=OuterRef("pk"), attribute=attribute, value__in=values
                )
                products = products.filter(Exists(match))
                active[f"attr_{attribute.slug}"] = values

    sort = params.get("sort")
    if sort in SORTS:
        active["sort"] = sort
        products = products.order_by(SORTS[sort][0], "-pk")
    elif q:
        products = products.order_by("-rank", "-created_at")
    else:
        products = products.order_by("-created_at")
    return products.distinct(), active


def filterable_attributes(category):
    return [a for a in category.all_attributes() if a.is_filterable]


def filter_options(products, category=None, params=None):
    """Brands and attribute values that exist in `products`, for the filter form."""
    ids = products.values("pk")
    options = {
        "brands": Brand.objects.filter(products__in=ids).distinct().order_by("name"),
        "conditions": Product.CONDITION_CHOICES,
        "sorts": [(key, label) for key, (_field, label) in SORTS.items()],
        "attributes": [],
    }
    if category is not None:
        for attribute in filterable_attributes(category):
            values = (
                ProductAttributeValue.objects.filter(attribute=attribute, product__in=ids)
                .values_list("value", flat=True)
                .distinct()
                .order_by("value")
            )
            if values:
                selected = params.getlist(f"attr_{attribute.slug}") if params else []
                options["attributes"].append((attribute, list(values), selected))
    return options
