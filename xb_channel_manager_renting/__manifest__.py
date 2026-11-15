# -*- coding: utf-8 -*-
{
    'name': 'Hotel OTA Channel Manager - Rental bridge',
    'summary': 'Channel Manager stays as Rental orders (pickup / return '
               'dates, nightly rental pricing, Hotel industry rooms).',
    'description': """
Bridge between the Hotel OTA Channel Manager and the Rental app.
Installs itself when both are installed: OTA reservations become rental
orders with pickup / return dates, the nightly rental pricing is used and
rental orders made at the front desk block the rooms on the channels.
""",
    'category': 'Sales/Rental',
    'version': '19.0.1.0.0',
    'author': 'XUBAX',
    'website': 'https://xubax.com',
    'license': 'OPL-1',
    'support': 'cristofferson28@gmail.com',
    'depends': [
        'xb_channel_manager',
        'sale_renting',
    ],
    'data': [
        'views/sale_order_views.xml',
    ],
    'post_init_hook': '_post_init_stay_dates',
    'images': ['static/description/banner.png'],
    'auto_install': True,
    'installable': True,
}
