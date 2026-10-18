# -*- coding: utf-8 -*-
{
    "name": "Self-Order Kiosk - Boutique Theme",
    "summary": "Dress your self-order kiosk like a boutique: large photos, your colors and "
               "fonts, a gallery with video, shop words on the buttons, installable as an app.",
    "description": """
Self-Order Kiosk - Boutique Theme
=================================
Odoo's kiosk is made for restaurants. This theme turns it into a shop window, set up
per kiosk in Point of Sale > Settings > Mobile self-order & Kiosk:

* Colors: main color, text, photo background and lines.
* Fonts: Cormorant Garamond, Playfair Display, Montserrat, Jost, Lato (SIL Open Font
  License, included) or the device's own.
* Square or rounded corners; 2, 3 or 4 product columns (one more on wide screens).
* Price in the list: price, "From" + the lowest price of the options, or none.
* Product page: main photo, swipe carousel, or a mosaic with the published video on top.
* Shop words on the buttons and titles ("View my selection", "Pay at the counter"...),
  your own text in every language if you want.
* Installable app: name, icon and bar color; opens full screen.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": ["pos_self_order"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/pos_self_order_index.xml",
    ],
    "assets": {
        "pos_self_order.assets": [
            "xb_self_order_boutique/static/src/app/boutique.js",
            "xb_self_order_boutique/static/src/app/boutique.xml",
            "xb_self_order_boutique/static/src/app/boutique.scss",
        ],
    },
    "images": ["static/description/banner.png"],
    "price": 59.0,
    "currency": "USD",
    "application": False,
    "installable": True,
    "auto_install": False,
}
