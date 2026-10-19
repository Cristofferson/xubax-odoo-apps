# -*- coding: utf-8 -*-
{
    'name': 'Showroom Wall — Self-service Kiosk',
    'version': '19.0.1.1.1',
    'category': 'Sales/Point of Sale',
    'summary': 'Customers send a piece from the self-service kiosk to the '
               'showroom wall.',
    'description': """
Showroom Wall — Self-service Kiosk
==================================

Bridge between *Showroom Wall* and Odoo's self-service kiosk. The product
page of the kiosk gets a **Show on the wall** button, so a customer browsing
on their own can see a piece in large on the showroom wall.

* Pick the wall each kiosk sends to in the Point of Sale settings.
* Only products ticked **Show on the showroom wall** get the button, and the
  server checks it again on every send.
* The wall shows whatever was sent last, from the kiosk or from a sales
  person's tablet. A sales person's comparison starts over instead of
  absorbing the piece a customer sent.
* Kiosk mode only: the QR menu opens on the customer's own phone, possibly
  far from the shop, and never drives the wall. A short pause between sends
  keeps a customer from taking the wall over.
""",
    'author': 'XUBAX',
    'website': 'https://www.xubax.com',
    'license': 'OPL-1',
    'images': ['static/description/banner.png'],
    'depends': ['xb_showroom_wall', 'pos_self_order'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'pos_self_order.assets': [
            'xb_showroom_wall_self_order/static/src/kiosk/*',
        ],
    },
    'installable': True,
    'auto_install': True,
    'application': False,
}
