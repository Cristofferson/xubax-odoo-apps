# -*- coding: utf-8 -*-
{
    "name": "Self-Order Kiosk - Quotation (Print / WhatsApp / Email)",
    "summary": "The customer gets a quotation of the kiosk cart, printed on the kiosk's "
               "printer, by WhatsApp and/or by email, created like the POS quotations.",
    "description": """
Self-Order Kiosk - Quotation (Print / WhatsApp / Email)
=======================================================
In the kiosk cart the customer can ask for a quotation:

* printed on the kiosk's receipt printer (ePOS printer set on the kiosk), and/or
* sent to their WhatsApp with the company's approved quotation template (needs
  WhatsApp, Odoo Enterprise: the free add-on "Self-Order Kiosk - Quotation -
  WhatsApp" installs itself when it is present), and/or
* sent to their email, with the quotation PDF (the same email as the "Send by
  email" button of Sales).

The customer leaves their name and, as each kiosk asks, their mobile (checked with
the rules of the company's country), their email, or both; and accepts your privacy
notice: the contact with that mobile or email is used, or created. Switch it on per
kiosk: Point of Sale settings > Mobile self-order & Kiosk > Quotations from the kiosk,
where you also choose what it asks for (Customer data). The quotation is created with the same function
as the POS quotations (Sales, Quotations & Layaway from POS): same validity, terms and
template, ready to be picked up at the counter from the POS orders list.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.4.0",
    "license": "OPL-1",
    "depends": ["pos_self_order", "phone_validation", "xb_sale_order_from_pos"],
    "data": [
        "views/kiosk_ticket_templates.xml",
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
    "price": 29.00,
    "currency": "USD",
}
