# -*- coding: utf-8 -*-
{
    "name": "WhatsApp Conversations - Inbox of all chats",
    "summary": "Conversaciones de WhatsApp agrupadas: one row per customer chat with the last "
               "message, newest first, the ones awaiting reply in bold. Click to answer.",
    "description": """
WhatsApp Conversations
======================
Odoo's WhatsApp menu lists every message on its own row, so following a customer means
reading a log. This module adds **WhatsApp > Conversations**: one row per chat, newest
first, like the inbox of your phone.

* Contact, number, business number (useful with several WhatsApp accounts), last message
  and its date.
* Chats where the customer wrote last are shown **in bold**, with the filter
  *Awaiting reply*.
* Group by business number, contact or day; search by name, number or contact.
* Click a row and the whole chat opens in Discuss, ready to answer.
* The native message-by-message list moves to *WhatsApp > Reports*.

Each user sees the chats Odoo already lets them see in Discuss. Nothing to configure.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Marketing/WhatsApp",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": ["whatsapp"],
    "data": [
        "views/discuss_channel_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "xb_whatsapp_conversations/static/src/scss/conversations.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "images": ["static/description/banner.png"],
    "application": False,
    "installable": True,
    "auto_install": False,
    "price": 8.00,
    "currency": "USD",
}
