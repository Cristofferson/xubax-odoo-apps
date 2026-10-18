# -*- coding: utf-8 -*-
{
    "name": "Self-Order Kiosk - Quotation - USB Printer (RawBT)",
    "summary": "When the kiosk prints on its own printer through RawBT, the quotation "
               "tells the customer to take the ticket from the kiosk, not from the counter.",
    "description": """
Bridge between *Self-Order Kiosk - Quotation* and *Self-Order Kiosk - USB Printer
(RawBT)*: installs itself when both are present.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": ["xb_self_order_quotation", "xb_self_order_rawbt"],
    "assets": {
        "pos_self_order.assets": [
            "xb_self_order_quotation_rawbt/static/src/app/quotation_rawbt.xml",
        ],
    },
    "images": ["static/description/banner.png"],
    "application": False,
    "installable": True,
    "auto_install": True,
}
