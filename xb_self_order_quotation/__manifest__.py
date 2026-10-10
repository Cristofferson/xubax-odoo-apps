# -*- coding: utf-8 -*-
{
    "name": "Self-Order Kiosk - Quotation (Print / WhatsApp)",
    "summary": "The customer gets a quotation of the kiosk cart, printed on the kiosk's "
               "printer and/or by WhatsApp, created like the POS quotations.",
    "description": """
Self-Order Kiosk - Quotation (Print / WhatsApp)
===============================================
In the kiosk cart the customer can ask for a quotation:

* printed on the kiosk's receipt printer (ePOS printer set on the kiosk), and/or
* sent to their WhatsApp with the company's approved quotation template.

The customer leaves their name and mobile (checked with the rules of the company's
country) and accepts your privacy notice: the contact with that mobile is used, or
created. Switch it on per kiosk: Point of Sale settings > Mobile self-order & Kiosk >
Quotations from the kiosk. The quotation is created with the same function
as the POS quotations (Sales, Quotations & Layaway from POS): same validity, terms and
template, ready to be picked up at the counter from the POS orders list.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.2.0",
    "license": "OPL-1",
    "depends": ["pos_self_order", "phone_validation", "xb_sale_order_from_pos_whatsapp"],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "pos_self_order.assets": [
            "xb_self_order_quotation/static/src/app/quotation.js",
            "xb_self_order_quotation/static/src/app/quotation.xml",
            "xb_self_order_quotation/static/src/app/quotation.scss",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
    "images": ["static/description/banner.png"],
    "price": 49.00,
    "currency": "USD",
}
