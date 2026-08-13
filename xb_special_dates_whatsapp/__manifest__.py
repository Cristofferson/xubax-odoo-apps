# -*- coding: utf-8 -*-
{
    "name": "Special Dates – WhatsApp Integration",
    "summary": "Send Special Dates greetings through WhatsApp, with the "
               "conversation context the agent needs to answer.",
    "description": """
Adds WhatsApp as a channel to the Communication Schedule of every
Special Date Type. Requires Odoo Enterprise with the ``whatsapp``
module installed and a configured Meta Business API account.

It also fixes a blind spot of the native WhatsApp integration: a template
sent from a business record is logged on that record, so when the customer
replies, the conversation that opens in Discuss contains only the reply. The
agent reads "yes, please" and has to guess what it answers.

With this module the greeting that was sent is mirrored into that
conversation as an internal note, right above the reply. It is done centrally
— on the single method every WhatsApp channel is created through — so it
covers every campaign you send as a template, not just Special Dates
reminders, and only for customers who actually answer, so a large send does
not fill Discuss with empty conversations.
""",
    "author": "Cristofferson Reyes",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Sales/Sales",
    "version": "19.0.1.2.0",
    "license": "OPL-1",
    "depends": [
        "xb_special_dates",
        "whatsapp",
    ],
    "data": [
        "views/xb_wish_schedule_views.xml",
    ],
    "images": [
        "static/description/banner.png",
    ],
    "auto_install": True,
    "installable": True,
    "price": 0.00,
    "currency": "USD",
}
