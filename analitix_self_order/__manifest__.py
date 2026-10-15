# -*- coding: utf-8 -*-
{
    "name": "Analitix - Self-Order Kiosk",
    "summary": "The kiosk's own camera measures who stops at the kiosk: how long, "
               "whether they use it, approximate age and gender, and whether it "
               "ends in a sale. Only numbers leave the tablet.",
    "description": """
Analitix - Self-Order Kiosk
===========================
The self-order kiosk becomes a measured point of attention in Analitix, with no
mini-PC and no door camera: the page of the kiosk reads its own front camera in
the browser.

For every person who stops in front of the kiosk, Analitix receives one row:
when, how long, how long they faced the screen, whether they touched it, how many
people were together, an approximate age band and gender, and whether the visit
ended in a kiosk order or a quotation in Sales.

No image leaves the tablet, ever: each frame is read in memory and dropped.
Switch it on per kiosk in the Point of Sale settings and put up the notice that
a camera is in use.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.2",
    "license": "OPL-1",
    "depends": ["analitix", "pos_self_order", "sale"],
    "data": [
        "security/ir.model.access.csv",
        "security/analitix_self_order_rules.xml",
        "data/ir_cron.xml",
        "views/analitix_kiosk_session_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "pos_self_order.assets": [
            "analitix_self_order/static/src/app/kiosk_camera.js",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
}
