# -*- coding: utf-8 -*-
{
    "name": "Sales, Quotations & Layaway from POS - Loyalty",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Quotation tickets say how many loyalty points the customer could "
               "earn by confirming, instead of points already won.",
    "description": """
Sales, Quotations & Layaway from POS - Loyalty
==============================================
A quotation created at the POS earns no loyalty points yet, but Odoo's ticket
prints them as already "Won". With this add-on a quotation ticket reads
"You could earn N loyalty points if you confirm this quotation" instead. Every
other ticket keeps Odoo's own line untouched.

Installs by itself when both Sales, Quotations & Layaway from POS and
Point of Sale Loyalty are present.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "company": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "license": "OPL-1",
    "depends": [
        "xb_sale_order_from_pos",
        "pos_loyalty",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "xb_sale_order_from_pos_loyalty/static/src/app/order_receipt.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": True,
}
