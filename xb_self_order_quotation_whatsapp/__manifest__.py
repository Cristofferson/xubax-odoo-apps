# -*- coding: utf-8 -*-
{
    "name": "Self-Order Kiosk - Quotation - WhatsApp",
    "summary": "The customer gets the kiosk quotation on their WhatsApp, with the "
               "company's approved quotation template.",
    "description": """
Self-Order Kiosk - Quotation - WhatsApp
=======================================
Adds "Send it to my WhatsApp" to Self-Order Kiosk - Quotation: the customer receives
the quotation ticket as the image of the company's approved WhatsApp quotation template
(the one set on the POS in Sales, Quotations & Layaway from POS - WhatsApp), and the
message is kept in the quotation's chatter.

Installs by itself when both Self-Order Kiosk - Quotation and Sales, Quotations &
Layaway from POS - WhatsApp (needs WhatsApp, Odoo Enterprise) are present.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": ["xb_self_order_quotation", "xb_sale_order_from_pos_whatsapp"],
    "data": [],
    "application": False,
    "installable": True,
    "auto_install": True,
    "images": ["static/description/banner.png"],
}
