"""Import products, variants and stock from a CSV file (Excel can save as CSV).

One row is one variant. Rows with the same title and category become one product.
A row with an existing SKU only adds stock: it never changes the product or the price.
"""

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.inventory import services
from apps.inventory.models import Lot

from .models import Attribute, Brand, Category, Product, ProductAttributeValue, Variant

COLUMNS = [
    "title",
    "category",
    "brand",
    "condition",
    "description",
    "sku",
    "variant",
    "price",
    "compare_at_price",
    "min_order_qty",
    "order_step",
    "quantity",
    "lot",
    "cost_per_unit",
]
REQUIRED = ["title", "category", "sku", "price"]
ATTR_PREFIX = "attr:"
CONDITIONS = {label.lower(): key for key, label in Product.CONDITION_CHOICES} | {
    key: key for key, _ in Product.CONDITION_CHOICES
}


class RowError(Exception):
    pass


@dataclass
class ImportResult:
    products_created: int = 0
    variants_created: int = 0
    stock_rows: int = 0
    errors: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.errors


def template_csv():
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([*COLUMNS, "attr:Color"])
    writer.writerow(
        [
            "Braided USB-C cable 1m",
            "Mobile accessories > Cables",
            "Baseus",
            "new",
            "Strong nylon cable.",
            "CAB-001",
            "Black",
            "650",
            "",
            "1",
            "1",
            "100",
            "DXB-2026-07",
            "300",
            "Black",
        ]
    )
    return out.getvalue()


def _money(value, name, required=False):
    value = (value or "").replace(",", "").strip()
    if not value:
        if required:
            raise RowError(f"{name} is required.")
        return None
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise RowError(f"{name} must be a number, not '{value}'.") from exc
    if amount < 0:
        raise RowError(f"{name} cannot be negative.")
    return amount.quantize(Decimal("1"))


def _int(value, name, default):
    value = (value or "").strip()
    if not value:
        return default
    if not value.isdigit():
        raise RowError(f"{name} must be a whole number, not '{value}'.")
    return int(value)


def _category(path, cache):
    if path in cache:
        return cache[path]
    parent = None
    for name in [p.strip() for p in path.split(">") if p.strip()]:
        parent = Category.objects.filter(name__iexact=name, parent=parent).first()
        if parent is None:
            raise RowError(f"Category '{path}' does not exist. Add it in the admin first.")
    if parent is None:
        raise RowError("Category is required.")
    cache[path] = parent
    return parent


def _attribute(name, cache):
    if name not in cache:
        cache[name] = Attribute.objects.filter(name__iexact=name).first()
    if cache[name] is None:
        raise RowError(f"Attribute '{name}' does not exist. Add it in the admin first.")
    return cache[name]


def _import_row(row, user, result, caches):
    for name in REQUIRED:
        if not (row.get(name) or "").strip():
            raise RowError(f"{name} is required.")
    sku = row["sku"].strip()
    quantity = _int(row.get("quantity"), "quantity", 0)
    lot_ref = (row.get("lot") or "").strip()
    lot = Lot.objects.get_or_create(reference=lot_ref)[0] if lot_ref else None
    cost = _money(row.get("cost_per_unit"), "cost_per_unit")
    price = _money(row["price"], "price", required=True)

    variant = Variant.objects.filter(sku=sku).first()
    if variant is None:
        category = _category(row["category"], caches["category"])
        condition_text = (row.get("condition") or "new").strip().lower()
        if condition_text not in CONDITIONS:
            raise RowError(f"Unknown condition '{row.get('condition')}'.")
        title = row["title"].strip()
        product = Product.objects.filter(title=title, category=category).first()
        if product is None:
            brand_name = (row.get("brand") or "").strip()
            product = Product.objects.create(
                title=title,
                category=category,
                brand=Brand.objects.get_or_create(name=brand_name)[0] if brand_name else None,
                condition=CONDITIONS[condition_text],
                description=(row.get("description") or "").strip(),
            )
            result.products_created += 1
        variant = Variant.objects.create(
            product=product,
            sku=sku,
            name=(row.get("variant") or "").strip(),
            price=price,
            compare_at_price=_money(row.get("compare_at_price"), "compare_at_price"),
            min_order_qty=_int(row.get("min_order_qty"), "min_order_qty", 1) or 1,
            order_step=_int(row.get("order_step"), "order_step", 1) or 1,
        )
        result.variants_created += 1
        for column, value in row.items():
            if column and column.lower().startswith(ATTR_PREFIX) and (value or "").strip():
                attribute = _attribute(column[len(ATTR_PREFIX) :].strip(), caches["attribute"])
                ProductAttributeValue.objects.update_or_create(
                    product=product, attribute=attribute, defaults={"value": value.strip()}
                )
    if quantity:
        services.receive(
            variant, quantity, lot=lot, cost_per_unit=cost, user=user, note="CSV import"
        )
        result.stock_rows += 1


def import_csv(file, user, dry_run=True):
    """Import all rows or none. With dry_run, check everything and then roll back."""
    result = ImportResult()
    try:
        text = file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        result.errors.append((0, "The file must be a CSV saved as UTF-8."))
        return result
    reader = csv.DictReader(io.StringIO(text))
    reader.fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED if c not in reader.fieldnames]
    if missing:
        result.errors.append((1, f"Missing columns: {', '.join(missing)}."))
        return result

    caches = {"category": {}, "attribute": {}}
    with transaction.atomic():
        for line, row in enumerate(reader, start=2):
            if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
                continue
            try:
                with transaction.atomic():
                    _import_row(row, user, result, caches)
            except RowError as exc:
                result.errors.append((line, str(exc)))
        if dry_run or result.errors:
            transaction.set_rollback(True)
    return result
