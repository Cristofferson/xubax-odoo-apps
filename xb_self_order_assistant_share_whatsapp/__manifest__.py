# -*- coding: utf-8 -*-
{
    "name": "Self-Order Kiosk - Virtual Seller - Send by WhatsApp",
    "summary": "The customer gets on their WhatsApp the products the virtual seller showed and the whole conversation.",
    "description": """
Adds "Send it to my WhatsApp" to the kiosk's Virtual Seller. The customer types their mobile
number on a big keypad (or asks the seller to send it) and receives, from the company's
WhatsApp number and with an approved template, a link to a page with the products they saw
and the whole conversation.

* The customer is found by the phone or created, and the conversation stays in their history.
* With CRM, an opportunity is created so a salesperson follows up.
* A button in the kiosk settings creates the WhatsApp template ready to submit to Meta.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": ["xb_self_order_assistant", "whatsapp"],
    "data": ["views/res_config_settings_views.xml"],
    "installable": True,
    "auto_install": True,
}
