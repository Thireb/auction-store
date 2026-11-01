from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalog.importer import import_csv, template_csv
from apps.catalog.models import Category, PriceTier, Product, ProductImage, Variant
from apps.inventory import levels, photos
from apps.inventory import services as stock
from apps.inventory.models import Lot, StockMovement

from ..access import portal_view
from ..forms import (
    COST_PERM,
    PRICE_PERM,
    ImageFormSet,
    ImportForm,
    ProductForm,
    StockChangeForm,
    TierFormSet,
    UploadImagesForm,
    VariantDetailForm,
    style_form,
    variant_formset,
)
from ..history import object_history

PAGE_SIZE = 50


def _page(request, queryset):
    page = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return page, query.urlencode()


@portal_view("catalog.view_product")
def product_list(request):
    products = Product.objects.select_related("category", "brand").prefetch_related(
        Prefetch("variants", queryset=Variant.objects.filter(is_active=True)),
        Prefetch("images", queryset=ProductImage.objects.order_by("sort_order", "pk")),
    )
    q = request.GET.get("q", "").strip()
    if q:
        products = products.filter(
            Q(title__icontains=q) | Q(variants__sku__icontains=q) | Q(origin_note__icontains=q)
        ).distinct()
    category_id = request.GET.get("category", "")
    if category_id.isdigit():
        category = Category.objects.filter(pk=category_id).first()
        if category:
            products = products.filter(category_id__in=category.descendant_ids())
    status = request.GET.get("status", "")
    if status == "active":
        products = products.filter(is_active=True)
    elif status == "hidden":
        products = products.filter(is_active=False)
    elif status == "in_stock":
        products = products.in_stock()
    elif status == "sold_out":
        products = products.out_of_stock()
    page, query_string = _page(request, products)
    context = {
        "page_obj": page,
        "query_string": query_string,
        "categories": Category.objects.select_related("parent__parent"),
        "q": q,
        "category_id": category_id,
        "status": status,
        "can_add": request.user.has_perm("catalog.add_product"),
    }
    return render(request, "portal/catalog/product_list.html", context)


def _save_images(request, product, upload_form, image_formset):
    user = request.user
    if user.has_perm("catalog.change_productimage") or user.has_perm("catalog.delete_productimage"):
        for form in image_formset.forms:
            if form.instance.pk is None:
                continue
            if image_formset.can_delete and form.cleaned_data.get("DELETE"):
                if user.has_perm("catalog.delete_productimage"):
                    # A tray photo goes back to its tray as unassigned.
                    photos.remove_image(form.instance, user)
            elif form.has_changed() and user.has_perm("catalog.change_productimage"):
                form.save()
    if user.has_perm("catalog.add_productimage"):
        start = product.images.count()
        for n, image in enumerate(upload_form.cleaned_data.get("images") or []):
            ProductImage.objects.create(
                product=product, image=image, alt_text=product.title, sort_order=start + n
            )


@portal_view("catalog.view_product")
def product_edit(request, pk=None):
    user = request.user
    product = get_object_or_404(Product, pk=pk) if pk else None
    if product is None and not user.has_perm("catalog.add_product"):
        raise PermissionDenied
    can_save = user.has_perm("catalog.change_product" if product else "catalog.add_product")
    posted = request.method == "POST" and can_save
    data, files = (request.POST, request.FILES) if posted else (None, None)

    category = None
    category_id = (data or request.GET).get("category")
    if category_id and str(category_id).isdigit():
        category = Category.objects.filter(pk=category_id).first()
    form = ProductForm(data, instance=product, category=category)
    variants = variant_formset(user, extra=1 if product else 0)(
        data, instance=product or Product(), prefix="variants"
    )
    images = ImageFormSet(
        data,
        queryset=product.images.all() if product else ProductImage.objects.none(),
        prefix="images",
    )
    upload = UploadImagesForm(data, files)
    lot_choices = Lot.objects.all()[:200]
    if posted and all(f.is_valid() for f in (form, variants, images, upload)):
        lot_id = request.POST.get("stock_lot") or None
        lot = Lot.objects.filter(pk=lot_id).first() if lot_id else None
        with transaction.atomic():
            product = form.save()
            form.save_attribute_values(product)
            variants.instance = product
            for variant_form in variants.forms:
                if not variant_form.has_changed() and variant_form.instance.pk is None:
                    continue
                variant_form.instance.product = product
                variant = variant_form.save()
                qty = variant_form.cleaned_data.get("add_stock")
                if qty:
                    stock.receive(variant, qty, lot=lot, user=user, note="Added on product page")
            _save_images(request, product, upload, images)
        messages.success(request, f"Saved “{product}”.")
        return redirect("portal:product_edit", product.pk)
    if not can_save:
        for f in [form, *variants.forms, *images.forms]:
            for field in f.fields.values():
                field.disabled = True
    context = {
        "product": product,
        "title": product.title if product else "New product",
        "form": form,
        "variants": variants,
        "images": images,
        "upload": upload,
        "lots": lot_choices,
        "can_save": can_save,
        "can_stock": user.has_perm("inventory.add_stockmovement"),
        "can_upload": user.has_perm("catalog.add_productimage"),
        "can_pick": product is not None
        and user.has_perms(["catalog.add_productimage", "inventory.view_lotphoto"]),
        "can_delete_images": user.has_perm("catalog.delete_productimage"),
        "can_delete": product is not None and user.is_superuser,
        "history": object_history(product) if product else [],
    }
    return render(request, "portal/catalog/product_form.html", context)


@portal_view("catalog.view_product")
def product_attributes(request):
    """HTMX: the attribute fields for the category picked in the product form."""
    category = Category.objects.filter(pk=request.GET.get("category") or 0).first()
    product = Product.objects.filter(pk=request.GET.get("product") or 0).first()
    form = ProductForm(instance=product, category=category)
    return render(request, "portal/catalog/partials/attributes.html", {"form": form})


@portal_view()
def product_delete(request, pk):
    if not request.user.is_superuser or request.method != "POST":
        raise PermissionDenied
    product = get_object_or_404(Product, pk=pk)
    variants = product.variants.all()
    if variants.filter(Q(order_items__isnull=False) | Q(stock_movements__isnull=False)).exists():
        messages.error(request, "This product has stock or orders. Hide it instead of deleting it.")
        return redirect("portal:product_edit", pk)
    product.delete()
    messages.success(request, f"Deleted “{product}”.")
    return redirect("portal:product_list")


@portal_view("catalog.view_variant")
def variant_detail(request, pk):
    user = request.user
    variant = get_object_or_404(Variant.objects.select_related("product"), pk=pk)
    can_change = user.has_perm("catalog.change_variant")
    can_price = user.has_perm(PRICE_PERM)
    action = request.POST.get("action") if request.method == "POST" else None

    form_class = type("VariantDetailFormForUser", (VariantDetailForm,), {"user": user})
    form = form_class(request.POST if action == "variant" else None, instance=variant)
    tiers = TierFormSet(
        request.POST if action == "tiers" else None, instance=variant, prefix="tiers"
    )
    stock_form = StockChangeForm(
        request.POST if action == "stock" else None, user=user, variant=variant
    )

    if action == "variant":
        if not can_change:
            raise PermissionDenied
        if form.is_valid():
            form.save()
            messages.success(request, "Variant saved.")
            return redirect("portal:variant_detail", pk)
    elif action == "tiers":
        if not can_price:
            raise PermissionDenied
        if tiers.is_valid():
            tiers.save()
            messages.success(request, "Bulk prices saved.")
            return redirect("portal:variant_detail", pk)
    elif action == "stock":
        if not user.has_perm("inventory.add_stockmovement"):
            raise PermissionDenied
        if stock_form.is_valid():
            d = stock_form.cleaned_data
            if d["kind"] == StockMovement.RECEIVED:
                stock.receive(
                    variant,
                    d["quantity"],
                    lot=d.get("lot"),
                    cost_per_unit=d.get("cost_per_unit"),
                    user=user,
                    note=d.get("note", ""),
                )
            else:
                stock.adjust(variant, d["quantity"], user=user, note=d["note"])
            messages.success(request, "Stock updated.")
            return redirect("portal:variant_detail", pk)

    if not can_change:
        for field in form.fields.values():
            field.disabled = True
    if not can_price:
        for f in tiers.forms:
            for field in f.fields.values():
                field.disabled = True
    context = {
        "variant": variant,
        "title": str(variant),
        "form": form,
        "tiers": tiers,
        "stock_form": stock_form,
        "can_change": can_change,
        "can_price": can_price,
        "can_stock": user.has_perm("inventory.add_stockmovement"),
        "show_cost": user.has_perm(COST_PERM),
        "stock_items": variant.stock_items.select_related("lot"),
        "movements": variant.stock_movements.select_related("lot", "user")[:50],
        "public_tiers": PriceTier.objects.filter(variant=variant),
        "history": object_history(variant),
    }
    return render(request, "portal/catalog/variant_detail.html", context)


@portal_view("catalog.view_variant")
def stock_list(request, level=None):
    fixed_level = bool(level)
    variants = levels.with_levels(
        Variant.objects.select_related("product__category").order_by("product__title", "sort_order")
    )
    q = request.GET.get("q", "").strip()
    if q:
        variants = variants.filter(
            Q(sku__icontains=q) | Q(name__icontains=q) | Q(product__title__icontains=q)
        )
    level = level or request.GET.get("level", "")
    if level == "low":
        variants = levels.near_empty(variants)
    elif level == "out":
        variants = levels.out_of_stock(variants)
    elif level == "in":
        variants = levels.in_stock(variants)
    category_id = request.GET.get("category", "")
    if category_id.isdigit():
        category = Category.objects.filter(pk=category_id).first()
        if category:
            variants = variants.filter(product__category_id__in=category.descendant_ids())
    page, query_string = _page(request, variants)
    context = {
        "page_obj": page,
        "query_string": query_string,
        "q": q,
        "level": level,
        "fixed_level": fixed_level,
        "title": {"low": "Near empty", "out": "Out of stock"}.get(level, "Stock levels"),
        "category_id": category_id,
        "categories": Category.objects.select_related("parent__parent"),
    }
    return render(request, "portal/stock/stock_list.html", context)


@portal_view("inventory.view_stockmovement")
def movement_list(request):
    movements = StockMovement.objects.select_related("variant__product", "lot", "user")
    q = request.GET.get("q", "").strip()
    if q:
        movements = movements.filter(
            Q(variant__sku__icontains=q)
            | Q(variant__product__title__icontains=q)
            | Q(reference__icontains=q)
            | Q(note__icontains=q)
        )
    kind = request.GET.get("kind", "")
    if kind:
        movements = movements.filter(kind=kind)
    lot = request.GET.get("lot", "")
    if lot.isdigit():
        movements = movements.filter(lot_id=lot)
    page, query_string = _page(request, movements)
    context = {
        "page_obj": page,
        "query_string": query_string,
        "q": q,
        "kind": kind,
        "kinds": StockMovement.KIND_CHOICES,
        "lot": lot,
        "lots": Lot.objects.all()[:200],
    }
    return render(request, "portal/stock/movement_list.html", context)


@portal_view(["catalog.add_product", "inventory.add_stockmovement"])
def import_view(request):
    if request.GET.get("template"):
        response = HttpResponse(template_csv(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="products-template.csv"'
        return response
    result, dry_run = None, True
    form = ImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        dry_run = form.cleaned_data["dry_run"]
        result = import_csv(form.cleaned_data["file"], request.user, dry_run=dry_run)
        if result.ok and not dry_run:
            messages.success(
                request,
                f"Imported {result.products_created} products, "
                f"{result.variants_created} variants and {result.stock_rows} stock rows.",
            )
    style_form(form)
    context = {"form": form, "result": result, "dry_run": dry_run, "title": "Import CSV"}
    return render(request, "portal/stock/import.html", context)
