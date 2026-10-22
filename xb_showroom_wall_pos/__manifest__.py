# -*- coding: utf-8 -*-
{
    'name': 'Showroom Wall — Point of Sale',
    'version': '19.0.1.2.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Cashiers send a piece from the point of sale to the '
               'showroom wall.',
    'description': """
Showroom Wall — Point of Sale
=============================

Bridge between *Showroom Wall* and the Point of Sale. The cashier shows a
piece in large on the showroom wall straight from the register:

* **Show on the wall** in the product information window (the *i* on a
  product), before the piece is even in the order.
* **Show on the wall** in the order's actions, for the selected line: the
  wall shows the exact version on the ticket (metal, size, stone...) and its
  price before any discount.
* **Compare** adds the piece next to the ones already on the wall, like
  *Compare* on the tablet. The wall goes back to its shop window by itself.
* Pick the wall each register sends to in the Point of Sale settings.
* Only products ticked **Show on the showroom wall** can be sent, and the
  server checks it again on every send, exactly like from the shop.
""",
    'author': 'XUBAX',
    'website': 'https://www.xubax.com',
    'license': 'OPL-1',
    'depends': ['xb_showroom_wall', 'point_of_sale'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'xb_showroom_wall_pos/static/src/pos/*',
        ],
    },
    'installable': True,
    'auto_install': True,
    'application': False,
}
