# -*- coding: utf-8 -*-
{
    "name": "Self-Order Kiosk - Virtual Seller + Kiosk Quotation",
    "summary": "\"Print me a quotation\": the virtual seller opens the kiosk quotation for the cart; it counts as her sale.",
    "description": """
Bridge between the kiosk's Virtual Seller and Self-Order Kiosk - Quotation: a quotation made at
the kiosk right after talking with the seller is credited to that conversation in the report
(sales and conversion), and the seller can open the kiosk's quotation window itself: printed at
the kiosk or sent to WhatsApp. Installs by itself when both apps are present.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": ["xb_self_order_assistant", "xb_self_order_quotation"],
    "data": [],
    "assets": {
        "pos_self_order.assets": [
            "xb_self_order_assistant_quotation/static/src/app/quote_action.js",
        ],
    },
    "installable": True,
    "auto_install": True,
}
