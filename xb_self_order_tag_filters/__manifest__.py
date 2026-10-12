# -*- coding: utf-8 -*-
{
    "name": "Self-Order Kiosk - Product Filters",
    "summary": "Product filters for the self-order kiosk: customers narrow a category by the "
               "shop's sections and tag groups. Four layouts, your colors.",
    "description": """
Self-Order Kiosk - Product Filters
==================================
Long categories are hard to browse standing at a kiosk. This module lets customers
narrow the products of a category, with large options built from what you already have:

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

Per kiosk (Point of Sale settings > Mobile self-order & Kiosk > Product filters):

* **Layout**: floating button with a panel, always-visible bar, a text line under the
  categories, or the main filter (e.g. Metal) in view and the rest in the panel.
* **Drawings**: none, the color of each tag, or the included jewelry drawings (stone
  shapes and metal colors).
* Counts on each option, the kiosk categories that offer filters, and your own colors.

Per filter: one option at a time (e.g. a single metal) or several.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.1.0",
    "license": "OPL-1",
    "depends": ["pos_self_order", "xb_website_sale_tag_groups"],
    "data": [
        "views/product_public_category_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "pos_self_order.assets": [
            "xb_self_order_tag_filters/static/src/app/*",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
    "images": ["static/description/banner.png"],
    "price": 39.00,
    "currency": "USD",
}
