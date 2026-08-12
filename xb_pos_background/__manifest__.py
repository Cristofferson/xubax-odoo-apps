# -*- coding: utf-8 -*-
{
    "name": "POS Background – Your Own Image and Logo on the Point of Sale",
    "summary": "Replace the default Odoo background image and the Odoo logo of "
               "the Point of Sale with your own, chosen per register from the "
               "POS settings.",
    "description": """
POS Background – Your Own Image and Logo on the Point of Sale
=============================================================

Out of the box, every Odoo Point of Sale shows the same generic background and
the Odoo logo on the screen your customers look at the longest: the standby
screen the register falls back to between sales, and the cashier login screen.

This module lets an administrator put **your own image and your own logo**
there, **for each Point of Sale separately** — the boutique gets its window
display, the coffee bar gets its own, the outlet gets the seasonal campaign.

What you can set, per Point of Sale
-----------------------------------
* **Background image** — replaces the default Odoo artwork on the standby
  screen and on the cashier login screen.
* **Background color** — painted behind the image; on its own, it turns the
  screen into a flat brand color with no image at all.
* **Image fit** — *Fill the screen*, *Fit the whole image*, *Tile* or *Center
  at original size*, so a wide photo, a tall poster and a small pattern all
  land properly on any screen shape.
* **Darkening** — a veil of black from 0 to 80 % over the image. This is the
  setting that turns a nice photo into a usable screen: the clock, the buttons
  and the logo stay readable over bright or busy pictures.
* **POS logo** — keep the Odoo logo, use your **company logo** in one click, or
  upload a **custom logo**. It replaces the Odoo logo both in the middle of the
  standby screen and in the POS top bar.

Everything is set in *Settings ▸ Point of Sale ▸ (your register) ▸
XUBAX - Background & Logo*. There is nothing to configure on the terminals:
open the Point of Sale and it is there.

Built to stay out of Odoo's way
-------------------------------
Odoo already draws those screens through CSS variables that the Point of Sale
leaves empty. This module simply fills them in, per register:

* **No core stylesheet is overwritten** and **no core template is patched**, so
  a Point of Sale with nothing configured looks exactly like a plain Odoo, and
  Odoo's own updates to those screens keep working.
* **The images never travel in the POS loading payload.** Odoo reads every
  field of ``pos.config`` when a session starts, so an image stored there would
  be sent, base64-encoded, to every terminal on every load. This module removes
  both images from that payload and sends short URLs instead: the browser
  downloads each image once and then serves it from its own cache. Your POS
  opens just as fast as before.
* **No new route, no public endpoint.** The images are served by Odoo's own
  ``/web/image``, which applies the reader's access rights unchanged.

Good to know
------------
* The **customer display** background is a standard Odoo 19 feature and is left
  alone: you will find it right above, in *Settings ▸ Point of Sale ▸ Customer
  Display*. This module does not duplicate it.
* The login screen appears when the *Cashiers* option (``pos_hr``) is enabled;
  the standby screen appears on every Point of Sale.
* Large photographs are resized to 1920 px on upload, as Odoo does everywhere
  else. A JPEG around 200–400 KB is plenty for a register screen.

Compatibility
-------------
* Odoo 19.0, Community and Enterprise.
* Point of Sale (``point_of_sale``) only. No other dependency.
""",
    "author": "Cristofferson Reyes",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "price": 18.00,
    "currency": "USD",
    "depends": [
        "point_of_sale",
    ],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "xb_pos_background/static/src/app/pos_background.js",
            "xb_pos_background/static/src/app/pos_background.scss",
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
