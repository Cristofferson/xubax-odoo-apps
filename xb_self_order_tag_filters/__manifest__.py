# -*- coding: utf-8 -*-
{
    "name": "Self-Order Kiosk - Product Filters",
    "summary": "A discreet floating \"Filter\" button in the self-order kiosk: customers narrow "
               "the products of a category by the shop's tag groups and sections.",
    "description": """
Self-Order Kiosk - Product Filters
==================================
Long categories are hard to browse standing at a kiosk. This module adds a small
floating **Filter** button over the product list of the self-order kiosk. It opens a
panel from the bottom with large options, built from what you already have:

* **Website sections**: give a website category a *kiosk filter title* (e.g. "Metal")
  and its subcategories (White gold, Yellow gold, Two-tone) become the first filter.
* **Tag filter groups** (from *eCommerce Tag Filter Groups*): one block per group
  (Style, Stone shape, Stones…).

Rules, as in the online shop: options of the same block add up (OR), different blocks
combine (AND). Each option shows how many products it leaves; options that would leave
none are greyed out. Only options that some product of the category has are shown, and
the button only appears in categories that have something to filter.

Filters start over when the customer changes category or the kiosk goes back to its
home screen, so the next customer starts clean.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": ["pos_self_order", "xb_website_sale_tag_groups"],
    "data": [
        "views/product_public_category_views.xml",
    ],
    "assets": {
        "pos_self_order.assets": [
            "xb_self_order_tag_filters/static/src/app/*",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
}
