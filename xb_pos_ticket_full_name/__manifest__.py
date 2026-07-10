# -*- coding: utf-8 -*-
{
    "name": "POS Receipt – Full Product Name (no truncation)",
    "summary": "Print the complete product name on POS receipts. Long names "
               "wrap onto several lines instead of being cut off with an ellipsis.",
    "description": """
POS Receipt – Full Product Name
===============================

Odoo applies the Bootstrap class ``text-truncate`` (``overflow: hidden``) to the
product name of each POS order line. On the **printed receipt** long product
names are **cut off** — the ticket shows only the start of the name followed by
``…`` — so neither the cashier nor the customer can read the full name of what
was sold. Tickets printed as an image through an **Epson / IoT thermal printer**
are the most affected, because the receipt is rasterised and the name stays on a
single line.

This module adds a small stylesheet to the Point of Sale receipt so that the
product name is **always printed in full**, wrapping onto as many lines as
needed. Over-long words (codes / SKUs) are also broken so nothing is ever
clipped, on the printed ticket and in its on-screen preview alike.

Key points
----------
* Long product names are **printed complete**, wrapping to several lines.
* Fixes the printed ticket (Epson / IoT raster) as well as the on-screen preview.
* Over-long words (codes / SKUs without spaces) are broken instead of cut.
* Scoped to the receipt (``.pos-receipt``): the on-screen cart keeps its
  compact, truncated look.
* Pure CSS — no Python, no data, **nothing to configure**. Install and print.

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
            "xb_pos_ticket_full_name/static/src/scss/xb_pos_ticket_full_name.scss",
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
