# -*- coding: utf-8 -*-
{
    "name": "Self-Order Kiosk - Virtual Seller + Showroom Wall",
    "summary": "The kiosk's virtual seller sends products to the showroom videowall: \"Look at the big screen!\"",
    "description": """
Bridge between the kiosk's Virtual Seller and the Showroom Wall (videowall). The seller can
put the product the customer likes on the wall, with the chosen options, alone or next to
others to compare them, with the same rules as the kiosk's "See it on the wall" button. The seller
can go with it: it appears small on the wall, with subtitles, and speaks from the wall speakers.
Installs by itself when both apps are present.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": ["xb_self_order_assistant", "xb_showroom_wall_self_order"],
    "data": ["views/res_config_settings_views.xml"],
    "installable": True,
    "auto_install": True,
}
