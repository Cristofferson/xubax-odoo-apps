# -*- coding: utf-8 -*-
{
    "name": "Sales, Quotations & Layaway from POS - WhatsApp",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Send the quotations created at the POS by WhatsApp: the same "
               "ticket that is printed.",
    "description": """
Sales, Quotations & Layaway from POS - WhatsApp
===============================================
Adds WhatsApp to the "How does the customer want the quotation?" question of
Sales, Quotations & Layaway from POS. The customer receives the very ticket the
POS prints, as the image header of an approved WhatsApp template, and the message
is kept in the quotation's chatter.

Installs by itself when both Sales, Quotations & Layaway from POS and WhatsApp
(Odoo Enterprise) are present.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "company": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "license": "OPL-1",
    "depends": [
        "xb_sale_order_from_pos",
        "whatsapp_sale",
    ],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": True,
}
