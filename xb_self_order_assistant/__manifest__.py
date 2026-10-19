# -*- coding: utf-8 -*-
{
    "name": "Self-Order Kiosk - Virtual Seller (AI)",
    "summary": "A virtual seller with a face and a voice on your kiosk: greets, talks and listens in any "
               "language, recommends your products with real prices, fills the cart and follows the "
               "customer to the videowall and their phone.",
    "description": """
Self-Order Kiosk - Virtual Seller (AI)
======================================
A seller with a face, a name and a voice on your self-order kiosk.

* Greets whoever stops in front of the kiosk (camera, nothing recorded), full screen or as a chat.
* Talks and listens hands-free, or by typing, in the customer's language.
* Searches the kiosk's catalog, puts her picks at the top of the product list with real
  prices (the exact combination of options) and adds products to the cart.
* Knows your shop (delivery, payment, warranty, hours) and sells the way you choose:
  consultative, balanced or sales-driven.
* Follows the customer to their phone (QR, NFC sticker) with the whole conversation.
* Calls a person: chat in Odoo, alert on the cash registers and/or e-mail.
* Reads barcodes and NFC cards (USB/Bluetooth reader or the tablet's NFC).
* Eleven realistic avatars (or yours), ten voices with adjustable accent and tone.
* Reports: every conversation with its products, cart, sale and cost; what customers
  looked for and did not find; weekly e-mail. Daily spending limit per kiosk.

Free add-ons: Showroom Wall (videowall), WhatsApp, Appointments, Kiosk Quotation, Analitix.

Uses Claude (Anthropic) to think and OpenAI to listen and speak, with your own API keys.
Manual in English and Spanish included (link in the settings).
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": ["pos_self_order", "mail"],
    "external_dependencies": {"python": ["anthropic", "requests"]},
    "data": [
        "security/ir.model.access.csv",
        "data/va_voice_data.xml",
        "data/va_avatar_data.xml",
        "views/va_avatar_views.xml",
        "views/res_config_settings_views.xml",
        "views/va_conversation_views.xml",
        "views/selection_page.xml",
        "views/mobile_page.xml",
        "views/weekly_digest.xml",
        "data/ir_cron.xml",
    ],
    "assets": {
        "pos_self_order.assets": [
            "xb_self_order_assistant/static/src/app/live.js",
            "xb_self_order_assistant/static/src/app/scan.js",
            "xb_self_order_assistant/static/src/app/presence.js",
            "xb_self_order_assistant/static/src/app/assistant.js",
            "xb_self_order_assistant/static/src/app/assistant.xml",
            "xb_self_order_assistant/static/src/app/assistant.scss",
            "xb_self_order_assistant/static/src/app/picks.js",
            "xb_self_order_assistant/static/src/app/picks.xml",
        ],
        "point_of_sale._assets_pos": [
            "xb_self_order_assistant/static/src/pos/handoff_alert.js",
        ],
    },
    "images": ["static/description/banner.png"],
    "price": 849.0,
    "currency": "USD",
    "application": False,
    "installable": True,
    "auto_install": False,
}
