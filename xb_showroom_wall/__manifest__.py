# -*- coding: utf-8 -*-
{
    'name': 'Showroom Wall',
    'version': '19.0.1.12.1',
    'category': 'Website/eCommerce',
    'summary': 'Send any product from your own web catalog to the showroom '
               'videowall from a tablet, in one tap.',
    'description': """
Showroom Wall
=============

Turns the shop assistant's tablet into a remote control for the showroom
screen. While the sales person browses the **real web catalog** with the
customer, a *Show on wall* button appears on every product (only for
signed-in internal users) and the big screen shows that piece full size,
with its video if it has one.

Highlights
----------
* **Built for multi-panel walls.** A 3x1 videowall is not a big 16:9 screen:
  the piece is drawn on the centre panel so the bezels never cut it, while
  the side panels carry the specs and a QR code.
* **Compare mode** — two to six pieces side by side, never cut by a bezel.
  With two or four, the centre screen lists what sets them apart. The
  tablet shows what is on the wall; one tap takes a single piece off.
* **Commercial names on two lines** — a product named «Verona · Solitary
  cathedral» shows «Verona» big and the rest below it, with the metal moving
  down to the data line. Comparing pieces uses that short name, and falls
  back to the reference when there is none.
* **Says what the customer picked** — the metal and size chosen on the
  product page travel to the wall, even when that version has no variant
  yet. Sent from the catalogue grid, the wall states only what holds for
  every version (``Available in 13 metals``).
* **One wall per branch** — each screen lists the sales people who may drive
  it, every tablet remembers its own wall (or is set once with
  ``/shop?showroom_screen=<id>``), and the server refuses a screen that is
  not the sales person's. With *Showroom Wall — Xibo* installed, a wall is
  published on its Xibo screen in one click.
* **Product video support** — plays the turning video published on the
  product, muted and looping.
* **Price visibility is a setting** — hide it, show a *from* figure, or show
  the full price. Jewellery shoppers usually come accompanied.
* **Idle fallback** — after a few quiet minutes the wall goes back to
  whatever it shows normally (a shop window page, a signage layout, ...).
* **No signage server required.** The wall page is a plain URL that polls
  Odoo, so it works inside any digital-signage web widget, a browser in
  kiosk mode or a smart TV.
""",
    'author': 'Cristofferson Reyes Rodriguez',
    'website': 'https://www.xubax.com',
    'license': 'OPL-1',
    'depends': ['website_sale'],
    'data': [
        'security/ir.model.access.csv',
        'security/showroom_security.xml',
        'views/showroom_screen_views.xml',
        'views/website_sale_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'xb_showroom_wall/static/src/js/showroom_push.css',
            'xb_showroom_wall/static/src/js/showroom_push.js',
        ],
    },
    'installable': True,
    'application': False,
}
