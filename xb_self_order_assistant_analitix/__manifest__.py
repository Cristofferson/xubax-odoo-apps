# -*- coding: utf-8 -*-
{
    "name": "Self-Order Kiosk - Virtual Seller + Analitix",
    "summary": "The virtual seller greets the people Analitix sees standing in front of the kiosk.",
    "description": """
Bridge between the kiosk's Virtual Seller and Analitix - Self-Order Kiosk. Analitix already
reads the kiosk camera to measure who stops in front of it; with this bridge the virtual seller
uses that same detection to greet them (no second camera reading). Installs by itself when both
apps are present.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": ["xb_self_order_assistant", "analitix_self_order"],
    "assets": {
        "pos_self_order.assets": [
            "xb_self_order_assistant_analitix/static/src/app/presence_analitix.js",
        ],
    },
    "installable": True,
    "auto_install": True,
}
