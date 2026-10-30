"""Demo catalog data for local tests. Used by `manage.py seed_demo`."""

import io
import random

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont

from .demo_extra import EXTRA_CATALOG, VARIANT_OPTIONS
from .models import (
    Attribute,
    Brand,
    Category,
    Product,
    ProductAttributeValue,
    ProductImage,
    Variant,
)

CATEGORIES = {
    "Furniture": ["Sofas", "Tables", "Chairs"],
    "Mobile accessories": ["Chargers", "Cables", "Phone cases", "Earbuds"],
    "Decor": ["Lamps", "Wall art", "Vases"],
    "Shoes": ["Men's shoes", "Women's shoes", "Sneakers"],
    "Watches": ["Smart watches", "Analog watches"],
}

ATTRIBUTES = [
    # name, type, choices, unit, categories
    ("Color", Attribute.CHOICE, "Black\nWhite\nBrown\nGrey\nBlue\nSilver", "", list(CATEGORIES)),
    (
        "Material",
        Attribute.CHOICE,
        "Wood\nMetal\nLeather\nFabric\nPlastic\nGlass",
        "",
        ["Furniture", "Decor", "Shoes"],
    ),
    ("Seats", Attribute.NUMBER, "", "", ["Sofas", "Chairs"]),
    ("Width", Attribute.NUMBER, "", "cm", ["Furniture"]),
    ("Size (EU)", Attribute.CHOICE, "39\n40\n41\n42\n43\n44", "", ["Shoes"]),
    ("Connector", Attribute.CHOICE, "USB-C\nLightning\nMicro USB", "", ["Chargers", "Cables"]),
    ("Power", Attribute.NUMBER, "", "W", ["Chargers"]),
    ("Strap type", Attribute.CHOICE, "Leather\nMetal\nSilicone\nFabric", "", ["Watches"]),
    ("Water resistant", Attribute.YES_NO, "", "", ["Watches"]),
]

BRANDS = ["Samsung", "Anker", "Baseus", "Casio", "Fossil", "IKEA", "Nike", "Adidas", "Home Centre"]

PRODUCTS = [
    # title, category, brand, condition, price, variants, attributes
    (
        "3-seater fabric sofa",
        "Sofas",
        "Home Centre",
        "used_like_new",
        85000,
        None,
        {"Color": "Grey", "Seats": "3", "Material": "Fabric", "Width": "210"},
    ),
    (
        "Leather recliner sofa",
        "Sofas",
        "Home Centre",
        "open_box",
        145000,
        None,
        {"Color": "Brown", "Seats": "2", "Material": "Leather"},
    ),
    (
        "Oak dining table",
        "Tables",
        "IKEA",
        "used_good",
        42000,
        None,
        {"Material": "Wood", "Width": "160"},
    ),
    (
        "Glass coffee table",
        "Tables",
        None,
        "new",
        18500,
        None,
        {"Material": "Glass", "Width": "100"},
    ),
    (
        "Office chair, mesh back",
        "Chairs",
        "IKEA",
        "open_box",
        14500,
        None,
        {"Color": "Black", "Seats": "1"},
    ),
    (
        "25W USB-C fast charger",
        "Chargers",
        "Samsung",
        "new",
        2200,
        None,
        {"Connector": "USB-C", "Power": "25"},
    ),
    (
        "65W GaN charger, 3 ports",
        "Chargers",
        "Anker",
        "new",
        6500,
        None,
        {"Connector": "USB-C", "Power": "65"},
    ),
    (
        "Braided USB-C cable 1m",
        "Cables",
        "Baseus",
        "new",
        650,
        [("1 m", 650), ("2 m", 850)],
        {"Connector": "USB-C", "Color": "Black"},
    ),
    (
        "Lightning cable 1m",
        "Cables",
        None,
        "new",
        550,
        None,
        {"Connector": "Lightning", "Color": "White"},
    ),
    (
        "Silicone case for iPhone 15",
        "Phone cases",
        None,
        "new",
        900,
        [("Black", 900), ("Blue", 900), ("White", 900)],
        {},
    ),
    ("Wireless earbuds with case", "Earbuds", "Anker", "open_box", 5200, None, {"Color": "White"}),
    (
        "Brass table lamp",
        "Lamps",
        None,
        "used_like_new",
        7800,
        None,
        {"Material": "Metal", "Color": "Brown"},
    ),
    (
        "Abstract canvas print",
        "Wall art",
        None,
        "new",
        4500,
        [("60x40 cm", 4500), ("90x60 cm", 7200)],
        {},
    ),
    (
        "Ceramic flower vase",
        "Vases",
        None,
        "new",
        2400,
        None,
        {"Material": "Glass", "Color": "White"},
    ),
    (
        "Leather formal shoes",
        "Men's shoes",
        None,
        "new",
        9500,
        [("41", 9500), ("42", 9500), ("43", 9500)],
        {"Material": "Leather", "Color": "Black"},
    ),
    (
        "Running sneakers",
        "Sneakers",
        "Nike",
        "open_box",
        12500,
        [("40", 12500), ("42", 12500), ("44", 12500)],
        {"Color": "White"},
    ),
    (
        "Women's heeled sandals",
        "Women's shoes",
        None,
        "new",
        4200,
        [("39", 4200), ("40", 4200)],
        {"Color": "Brown"},
    ),
    (
        "Galaxy smart watch",
        "Smart watches",
        "Samsung",
        "open_box",
        32000,
        None,
        {"Strap type": "Silicone", "Water resistant": "Yes", "Color": "Black"},
    ),
    (
        "Fitness band",
        "Smart watches",
        None,
        "new",
        3800,
        None,
        {"Strap type": "Silicone", "Water resistant": "Yes"},
    ),
    (
        "Classic analog watch",
        "Analog watches",
        "Casio",
        "new",
        8900,
        None,
        {"Strap type": "Metal", "Water resistant": "Yes", "Color": "Silver"},
    ),
    (
        "Chronograph leather watch",
        "Analog watches",
        "Fossil",
        "used_like_new",
        21000,
        None,
        {"Strap type": "Leather", "Color": "Brown"},
    ),
]


IMAGE_VIEWS = ["Front", "Side", "Detail"]


def _wrap(text, width):
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return [*lines, line]


def placeholder_image(text, seed, label=""):
    """A product photo stand-in: a colored gradient, a simple shape and the title."""
    rng = random.Random(seed)
    top = tuple(rng.randint(150, 235) for _ in range(3))
    bottom = tuple(max(c - 70, 30) for c in top)
    size = 600
    img = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(img)
    for y in range(size):
        t = y / size
        draw.line(
            [(0, y), (size, y)],
            fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom, strict=True)),
        )
    shade = tuple(max(c - 110, 10) for c in top)
    box = (150, 120, 450, 360)
    if seed % 3 == 0:
        draw.ellipse(box, fill=shade)
    elif seed % 3 == 1:
        draw.rounded_rectangle(box, radius=40, fill=shade)
    else:
        draw.polygon([(300, 110), (460, 370), (140, 370)], fill=shade)
    title_font = ImageFont.load_default(size=38)
    small_font = ImageFont.load_default(size=24)
    y = 400
    for line in _wrap(text, 24)[:3]:
        width = draw.textlength(line, font=title_font)
        draw.text(((size - width) / 2, y), line, fill=(20, 20, 20), font=title_font)
        y += 46
    if label:
        draw.text((24, 22), label, fill=(30, 30, 30), font=small_font)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=82)
    return ContentFile(buffer.getvalue())


def generated_products():
    """The products of EXTRA_CATALOG, in the same shape as PRODUCTS, plus the parent name."""
    rng = random.Random(2026)
    conditions = ["new", "new", "new", "open_box", "open_box", "used_like_new", "used_good"]
    for parent, children in EXTRA_CATALOG.items():
        for child, (brands, (low, high), kind, names) in children.items():
            for name in names:
                brand = rng.choice(brands)
                price = round(rng.randint(low, high), -2 if high > 5000 else -1)
                variants = None
                if kind:
                    variants = [
                        (option, round(price * (1 + extra), -1))
                        for option, extra in VARIANT_OPTIONS[kind]
                    ]
                attrs = {}
                if kind != "color":
                    attrs["Color"] = rng.choice(["Black", "White", "Brown", "Grey", "Blue"])
                yield (
                    f"{brand} {name}",
                    child,
                    brand,
                    rng.choice(conditions),
                    price,
                    variants,
                    attrs,
                    parent,
                )


def _categories():
    """Parent name -> child names, from CATEGORIES and EXTRA_CATALOG."""
    tree = {parent: list(children) for parent, children in CATEGORIES.items()}
    for parent, children in EXTRA_CATALOG.items():
        names = tree.setdefault(parent, [])
        names.extend(child for child in children if child not in names)
    return tree


def _create_product(row, sku_prefix, index, categories, brands, attributes):
    title, cat, brand, condition, price, variants, attrs = row
    product = Product.objects.create(
        title=title,
        category=categories[cat],
        brand=brands.get(brand),
        condition=condition,
        description=(
            f"{title}. Imported from a Dubai auction lot or export leftover stock. "
            "Checked and photographed by our team before listing."
        ),
        origin_note="Dubai auction, demo lot",
        is_featured=index % 5 == 0,
    )
    for n, (name, variant_price) in enumerate(variants or [("", price)]):
        Variant.objects.create(
            product=product,
            sku=f"{sku_prefix}{index:03d}-{n}",
            name=name,
            price=variant_price,
            compare_at_price=round(variant_price * 1.3, -2) if index % 3 == 0 else None,
            sort_order=n,
        )
    for name, value in attrs.items():
        ProductAttributeValue.objects.create(
            product=product, attribute=attributes[name], value=value
        )
    for n, view in enumerate(IMAGE_VIEWS):
        image = ProductImage(product=product, alt_text=f"{title}, {view.lower()}", sort_order=n)
        image.image.save(
            f"{sku_prefix.lower()}{index:03d}-{n}.jpg",
            placeholder_image(title, len(sku_prefix) * 10000 + index * 10 + n, view),
            save=True,
        )


def seed_catalog(stdout=None):
    categories = {}
    for order, (parent_name, children) in enumerate(_categories().items()):
        parent, _ = Category.objects.get_or_create(
            name=parent_name, parent=None, defaults={"sort_order": order}
        )
        categories[parent_name] = parent
        for child_order, child_name in enumerate(children):
            child, _ = Category.objects.get_or_create(
                name=child_name, parent=parent, defaults={"sort_order": child_order}
            )
            categories[child_name] = child

    attributes = {}
    for order, (name, type_, choices, unit, cat_names) in enumerate(ATTRIBUTES):
        attr, _ = Attribute.objects.get_or_create(
            name=name,
            defaults={"type": type_, "choices": choices, "unit": unit, "sort_order": order},
        )
        if name == "Color":
            cat_names = [*cat_names, *EXTRA_CATALOG]
        attr.categories.add(*[categories[c] for c in cat_names])
        attributes[name] = attr

    brand_names = {*BRANDS, *(row[2] for row in generated_products())}
    brands = {name: Brand.objects.get_or_create(name=name)[0] for name in brand_names}

    rows = [("DEMO-", i, row) for i, row in enumerate(PRODUCTS)]
    rows += [("DEMO-G", i, row[:7]) for i, row in enumerate(generated_products())]
    created = 0
    for sku_prefix, index, row in rows:
        if Product.objects.filter(title=row[0]).exists():
            continue
        _create_product(row, sku_prefix, index, categories, brands, attributes)
        created += 1

    if stdout:
        stdout.write(f"Catalog: {len(categories)} categories, {created} new products.")
