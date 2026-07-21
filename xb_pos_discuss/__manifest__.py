# -*- coding: utf-8 -*-
{
    "name": "POS Discuss – Odoo Chat inside the Point of Sale",
    "summary": "Adds a Discuss button with a live unread badge to the POS navbar. "
               "Cashiers read and answer their Odoo Discuss messages without "
               "leaving the Point of Sale — the real Discuss, not a copy.",
    "description": """
POS Discuss – Odoo Chat inside the Point of Sale
================================================

Cashiers spend their whole shift on the Point of Sale screen, where Odoo gives
them no way to see the messages the rest of the company sends them. To answer a
question from the office they have to leave the POS, open the back office, read
Discuss and come back.

This module puts a **Discuss button in the POS navbar**, with a badge showing
how many unread messages are waiting, and opens **the real Odoo Discuss** in a
panel over the Point of Sale.

What the cashier gets
---------------------
* The **same channels and the same messages** as Discuss outside the POS.
* The **native Discuss interface**: identical message styling, avatars,
  threads, replies, reactions, emojis, attachments, mentions and search. It is
  not a re-implementation, so it looks and behaves exactly like the Discuss
  your users already know — and it keeps up with Odoo automatically.
* A panel that opens over the POS and closes again: **the current order is
  never lost** and the session is not interrupted.

A badge that shows the same number as Odoo
------------------------------------------
The badge repeats the count of the Discuss systray in the back office, from
Odoo's own read state. Odoo does **not** count unread messages: a conversation
with forty pending messages counts **one**, like a conversation with one, and
muted or closed conversations count nothing.

* Messages read anywhere — Discuss on the web, on the phone, in the systray —
  **stop counting in the POS too**.
* Messages read in the POS panel stop counting everywhere else.
* The badge empties while the panel is open, as the cashier reads.
* **No new field is added to** ``mail.message``, no read flags are duplicated
  and no message is ever created outside the standard Discuss flow.

Configuration
-------------
One switch per Point of Sale in *Settings ▸ Point of Sale ▸ XUBAX - Discuss*
(on by default). Nothing else to set up.

Technical notes
---------------
* The panel embeds the standard Discuss action of the same Odoo session, so
  every access right, channel membership and notification setting applies
  unchanged. The back-office top bar is hidden inside the panel: cashiers get
  Discuss, not the whole back office.
* Cashiers need a normal internal user account (the standard requirement for
  operating a POS).
* Only one small request every 15 seconds per terminal to refresh the badge;
  the conversation itself is kept live by Discuss through the bus.

Compatibility
-------------
* Odoo 19.0 Community and Enterprise.
* Point of Sale (``point_of_sale``) and Discuss (``mail``).
""",
    "author": "Cristofferson Reyes",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.3",
    "license": "OPL-1",
    "price": 49.00,
    "currency": "USD",
    "depends": [
        "point_of_sale",
        "mail",
    ],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "xb_pos_discuss/static/src/app/navbar/pos_discuss.js",
            "xb_pos_discuss/static/src/app/navbar/pos_discuss.xml",
            "xb_pos_discuss/static/src/app/navbar/pos_discuss.scss",
        ],
    },
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
}
