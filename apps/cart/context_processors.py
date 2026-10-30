from .cart import SESSION_KEY


def cart_count(request):
    items = request.session.get(SESSION_KEY, {}) if hasattr(request, "session") else {}
    return {"cart_count": sum(int(q) for q in items.values())}
