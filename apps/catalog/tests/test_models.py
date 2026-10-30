import pytest
from django.core.exceptions import ValidationError

from apps.catalog.models import Attribute, Product

from .factories import AttributeFactory, CategoryFactory, ProductFactory, VariantFactory

pytestmark = pytest.mark.django_db


def test_slug_is_made_unique():
    a = ProductFactory(title="Leather Sofa")
    b = ProductFactory(title="Leather Sofa")
    assert a.slug == "leather-sofa"
    assert b.slug == "leather-sofa-2"


def test_category_tree_helpers():
    root = CategoryFactory(name="Watches")
    child = CategoryFactory(name="Smart watches", parent=root)
    grandchild = CategoryFactory(name="Kids", parent=child)
    assert str(grandchild) == "Watches > Smart watches > Kids"
    assert set(root.descendant_ids()) == {root.pk, child.pk, grandchild.pk}
    assert child.descendant_ids(include_self=False) == [grandchild.pk]


def test_category_cannot_be_its_own_parent():
    root = CategoryFactory()
    child = CategoryFactory(parent=root)
    root.parent = child
    with pytest.raises(ValidationError):
        root.clean()


def test_child_category_inherits_attributes():
    root = CategoryFactory()
    child = CategoryFactory(parent=root)
    color = AttributeFactory(name="Color")
    color.categories.add(root)
    strap = AttributeFactory(name="Strap")
    strap.categories.add(child)
    assert set(child.all_attributes()) == {color, strap}
    assert list(root.all_attributes()) == [color]


def test_choice_attribute_needs_options():
    attr = Attribute(name="Size", type=Attribute.CHOICE, choices="\n \n")
    with pytest.raises(ValidationError):
        attr.clean()
    attr.choices = "S\nM\nL"
    attr.clean()
    assert attr.choice_list == ["S", "M", "L"]


def test_min_price_uses_active_variants_only():
    product = ProductFactory()
    VariantFactory(product=product, price=900, is_active=False)
    VariantFactory(product=product, price=1500)
    VariantFactory(product=product, price=1200)
    assert product.min_price == 1200


def test_visible_hides_inactive_products_and_categories():
    shown = ProductFactory()
    ProductFactory(is_active=False)
    ProductFactory(category=CategoryFactory(is_active=False))
    assert list(Product.objects.visible()) == [shown]


def test_bulky_and_advance_rules_inherit_from_category():
    from apps.catalog.models import ADVANCE_FIXED, ADVANCE_NONE, ADVANCE_PERCENT

    furniture = CategoryFactory(is_bulky=True, advance_type=ADVANCE_PERCENT, advance_value=20)
    sofas = CategoryFactory(parent=furniture)
    sofa = ProductFactory(category=sofas)
    assert sofa.bulky
    assert sofa.advance_rule() == (ADVANCE_PERCENT, 20)

    sofa.is_bulky, sofa.advance_type, sofa.advance_value = False, ADVANCE_FIXED, 5000
    assert not sofa.bulky
    assert sofa.advance_rule() == (ADVANCE_FIXED, 5000)

    assert ProductFactory().advance_rule() == (ADVANCE_NONE, 0)
