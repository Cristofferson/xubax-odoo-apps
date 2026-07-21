POS Discuss – Odoo Chat inside the Point of Sale
================================================

A Discuss button in the Point of Sale navbar, right next to the cashier avatar,
with a badge for unread messages. Clicking it opens **the real Odoo Discuss**
over the POS.

* Author: **Cristofferson Reyes** (XUBAX)
* License: OPL-1
* Compatible with: **Odoo 19.0** Community and Enterprise

The problem
-----------

Cashiers spend their whole shift on the Point of Sale screen, and Odoo gives
them no way to see the messages the rest of the company sends them there. To
read a question from the office they have to leave the POS, open the back
office, go to Discuss and come back to the register.

What this module does
---------------------

* Adds a **Discuss button to the POS navbar**, immediately to the left of the
  cashier avatar, with a badge showing the number of unread messages.
* Opens **the standard Discuss interface** in a panel over the POS: the same
  channels, the same messages, the same styling, avatars, threads, replies,
  reactions, emojis, attachments, mentions and search.
* The panel opens and closes over the POS, so **the order in progress is never
  lost** and the session is not interrupted.

An unread counter that tells the truth
--------------------------------------

The badge is computed from Odoo's own read state
(``discuss.channel.member.message_unread_counter``) — the very counter the
Discuss menu uses:

* Messages read anywhere (Discuss on the web, on the phone, in the systray)
  **stop counting in the POS too**, and the other way round.
* Muted channels are skipped, like the native messaging menu.
* **No field is added to** ``mail.message``, no read flags are duplicated, and
  no message is created outside the standard Discuss flow.

Configuration
-------------

*Settings ▸ Point of Sale ▸ XUBAX - Discuss ▸ Discuss in the POS* — one switch
per Point of Sale, enabled by default. Nothing else to set up.

Technical notes
---------------

* The panel embeds the standard Discuss action of the same Odoo session, so
  every access right, channel membership and notification setting applies
  unchanged. The back-office top bar is hidden inside the panel, so cashiers
  get Discuss and not a door into the back office.
* Cashiers need a normal internal user account — the standard requirement for
  operating a Point of Sale.
* While the panel is closed the terminal makes one small request every 15
  seconds to refresh the badge; while it is open, Discuss keeps itself live
  through the bus.

Support
-------

soporte@xubax.com — https://www.xubax.com
