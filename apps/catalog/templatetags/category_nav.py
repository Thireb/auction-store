from django import template

from .. import nav

register = template.Library()


@register.inclusion_tag("catalog/partials/category_nav.html", takes_context=True)
def category_nav(context):
    """The left sidebar. Opens the branch of the category or product on the page."""
    current = context.get("category")
    product = context.get("product")
    if current is None and product is not None and hasattr(product, "category"):
        current = product.category
    request = context.get("request")
    return {"nodes": nav.tree(current, request), "current": current, "request": request}


@register.filter
def open_node(nodes):
    """The id of the node whose branch starts open, for Alpine, or "null"."""
    for node in nodes:
        if getattr(node, "on_path", False) and node.has_children:
            return node.pk
    return "null"


@register.simple_tag(takes_context=True)
def top_categories(context, limit=6):
    """Top-level categories for the header links."""
    return nav.roots(context.get("request"))[:limit]
