# -*- coding: utf-8 -*-
{
    "name": "Sales, Quotations & Layaway from POS - WhatsApp",
    "version": "19.0.1.3.0",
    "category": "Point of Sale",
    "summary": "Send the quotations created at the POS by WhatsApp (the same ticket "
               "that is printed) and notify customers about their orders by WhatsApp: "
               "ready, pick-up and balance reminders, a detail to confirm, or a delay "
               "with its new delivery date.",
    "description": """
Sales, Quotations & Layaway from POS - WhatsApp
===============================================
* Adds WhatsApp to the "How does the customer want the quotation?" question of
  Sales, Quotations & Layaway from POS. The customer receives the very ticket the
  POS prints, as the image header of an approved WhatsApp template, and the message
  is kept in the quotation's chatter.
* Notices about an order, under ONE button on each order / layaway of the orders
  list (Sales, and the list the POS opens to recover an order) and on the order form.
  It opens a window where the seller picks what to tell the customer, reads the exact
  message and sends it with the company's approved template:

  - the order is ready, with the balance still due (it remembers when it was told);
  - reminder: the ready order is still waiting to be picked up;
  - reminder: the balance still due on the order or layaway;
  - we need to confirm a detail (size, engraving...): it opens the conversation, so the
    seller can write freely once the customer replies;
  - there is a delay: the seller picks the new delivery date and apologises. That date
    becomes the order's delivery date, and the "ready" mark is cleared.

  Each notice is offered only when the company has its approved template and it makes
  sense for the order (no balance reminder on a paid order, for instance).

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
        "security/ir.model.access.csv",
        "security/xb_wa_rules.xml",
        "data/notice_type_data.xml",
        "data/ir_cron_data.xml",
        "views/res_config_settings_views.xml",
        "views/sale_order_views.xml",
        "wizard/sale_order_whatsapp_notice_views.xml",
        "views/quotation_ticket_image_templates.xml",
        "views/sale_order_wa_journey_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "xb_sale_order_from_pos_whatsapp/static/src/chatter/chatter_whatsapp_patch.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": True,
}
