# -*- coding: utf-8 -*-
{
    "name": "Sales, Quotations & Layaway from POS - Loyalty",
    "version": "19.0.1.0.1",
    "category": "Point of Sale",
    "summary": "Tickets of quotations, orders and layaways created at the POS say how "
               "many loyalty points the customer will earn, instead of points already won.",
    "description": """
Sales, Quotations & Layaway from POS - Loyalty
==============================================
When a quotation, order or layaway is created at the POS nothing is paid yet, so no
loyalty points are earned, but Odoo's ticket prints them as already "Won". With this
add-on the ticket printed on creation says instead:

* Quotation: "You could earn N loyalty points if you confirm this quotation"
* Order / layaway: "You will earn N loyalty points when this order is paid in full"

Advance and settlement tickets are real payments and keep Odoo's own line, as does
every regular sale.

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
