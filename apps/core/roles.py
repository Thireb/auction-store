"""Default staff roles.

Each role is a Django group. The owner (a superuser) can change these groups in the admin
at any time. `manage.py setup_roles` creates the groups and adds these permissions.
A permission whose model does not exist yet is skipped, so later phases only add lines here.

Staff roles never get permissions on users or groups: only the owner manages staff.
"""

INVENTORY_MANAGER = "Inventory manager"
ORDER_MANAGER = "Order manager"

ROLES = {
    INVENTORY_MANAGER: [
        "catalog.add_category",
        "catalog.change_category",
        "catalog.view_category",
        "catalog.add_attribute",
        "catalog.change_attribute",
        "catalog.view_attribute",
        "catalog.add_brand",
        "catalog.change_brand",
        "catalog.view_brand",
        "catalog.add_product",
        "catalog.change_product",
        "catalog.view_product",
        "catalog.add_variant",
        "catalog.change_variant",
        "catalog.view_variant",
        "catalog.view_pricetier",
        "catalog.add_productimage",
        "catalog.change_productimage",
        "catalog.delete_productimage",
        "catalog.view_productimage",
        "inventory.add_lot",
        "inventory.change_lot",
        "inventory.view_lot",
        "inventory.add_stockmovement",
        "inventory.view_stockmovement",
        "inventory.view_stockitem",
    ],
    ORDER_MANAGER: [
        "orders.view_order",
        "orders.change_order",
        "orders.view_orderitem",
        "orders.view_orderstatushistory",
        "orders.view_shipment",
        "orders.view_blockedphone",
        "orders.add_blockedphone",
        "shipping.view_city",
        "catalog.view_product",
        "catalog.view_variant",
    ],
}
