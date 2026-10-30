"""The category tree in the store's left sidebar.

The store can have a very large number of categories, so the page only renders the top
level and the branch of the category the customer is in. Other branches load with HTMX
when the customer opens them.
"""

from django.db.models import Exists, OuterRef

from .models import Category

SEARCH_LIMIT = 30


def active_categories():
    children = Category.objects.filter(parent=OuterRef("pk"), is_active=True)
    return Category.objects.filter(is_active=True).annotate(has_children=Exists(children))


def children_of(parent_id):
    return list(active_categories().filter(parent_id=parent_id).only("name", "slug", "parent"))


def tree(current=None):
    """Top-level nodes. The nodes on the path to `current` carry their loaded `children`."""
    path = current.ancestors(include_self=True) if current else []
    path_ids = [c.pk for c in path]
    nodes = children_of(None)
    level = nodes
    for depth, category_id in enumerate(path_ids):
        node = next((n for n in level if n.pk == category_id), None)
        if node is None:
            break
        node.on_path = True
        node.is_current = depth == len(path_ids) - 1
        if node.has_children:
            node.loaded_children = children_of(node.pk)
            level = node.loaded_children
    return nodes


def search(query):
    if not query:
        return []
    return list(
        active_categories()
        .filter(name__icontains=query)
        .select_related("parent__parent")
        .order_by("name")[:SEARCH_LIMIT]
    )
