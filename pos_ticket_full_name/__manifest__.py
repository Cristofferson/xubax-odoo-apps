# -*- coding: utf-8 -*-
{
    "name": "POS Receipt – Full Product Name (no truncation)",
    "summary": "Print the complete product name on POS receipts. Long names "
               "wrap onto several lines instead of being cut off with an ellipsis.",
    "description": """
POS Receipt – Full Product Name
===============================

Odoo applies the Bootstrap class ``text-truncate`` to the product name of each
order line (``overflow: hidden``). On the **POS receipt** this cuts off long
product names — especially long codes/SKUs or names with few spaces to wrap on —
so the printed ticket ends in ``…`` or a chopped word and neither the cashier
nor the customer can read the full name of what was sold.

This module adds a small stylesheet to the Point of Sale receipt so that,
**inside the receipt only**, the product name is **always printed in full**,
wrapping onto as many lines as needed. Very long words (SKUs, codes) are broken
so they never overflow the paper width and nothing is ever clipped.

Key points
----------
* The full product name is **always printed**, wrapping to several lines.
* Long codes / names without spaces are broken instead of being cut off.
* Scoped to the receipt (``.pos-receipt``): the on-screen cart keeps its
  compact, truncated look.
* Pure CSS — no Python, no data, **nothing to configure**. Install and print.
* Works with any receipt printer (the change is in the receipt markup, so it
  applies to the on-screen preview and to the printed ticket alike).

Compatibility
-------------
* Odoo 18.0 Community and Enterprise.
* Point of Sale (``point_of_sale``).
""",
    "author": "Cristofferson Reyes",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "depends": [
        "point_of_sale",
    ],
    "data": [],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_ticket_full_name/static/src/scss/pos_ticket_full_name.scss",
        ],
    },
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
}
