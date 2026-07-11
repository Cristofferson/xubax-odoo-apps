# -*- coding: utf-8 -*-
{
    'name': 'POS Food Delivery: Uber Eats & DiDi Food (Mexico)',
    'summary': 'Connect the Restaurant POS directly to Uber Eats and DiDi Food: '
               'menu sync, live order intake with sound alerts, accept/reject, '
               'courier tracking and automatic payments. No aggregator fees.',
    'description': """
POS Food Delivery: Uber Eats & DiDi Food
========================================
Direct integration between the Odoo Restaurant Point of Sale and the two main
food delivery platforms in Mexico and Latin America:

* **Uber Eats** (Marketplace API) — official direct integration.
* **DiDi Food** (Open Platform) — official direct integration.

No middleman, no monthly aggregator fee: your Odoo talks straight to the
delivery platforms.

Features
--------
* One-click **menu synchronization** from your POS categories, products,
  variants and attributes (modifier groups), with a dedicated pricelist per
  platform and photos.
* **Live order intake**: new delivery orders pop up in the POS with a looping
  sound alert, ready to accept or reject.
* Auto-accept mode, preparation time control and sold-out toggles pushed to
  the platforms in real time.
* Orders flow to the kitchen like any POS order (kitchen printers /
  preparation display).
* **Courier tracking** and delivery status inside the POS.
* Automatic payment registration per platform (dedicated journal & payment
  method) for clean session closing and accounting.
* Store online/offline control per platform from the POS.
* Full webhook security (signatures + secret URLs) and request log.
* Demo order wizard to try the whole flow without API credentials.
""",
    'category': 'Sales/Point of Sale',
    'version': '19.0.1.0.0',
    'author': 'Cristofferson Reyes Rodriguez',
    'website': 'https://xubax.com',
    'license': 'OPL-1',
    'price': 249.00,
    'currency': 'USD',
    'support': 'cristofferson28@gmail.com',
    'depends': [
        'point_of_sale',
        'pos_restaurant',
        'account',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/product_data.xml',
        'data/cron.xml',
        'views/xb_delivery_account_views.xml',
        'views/xb_delivery_log_views.xml',
        'views/pos_order_views.xml',
        'views/product_views.xml',
        'views/menus.xml',
        'wizard/xb_delivery_test_order_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'xb_pos_delivery/static/src/app/**/*',
        ],
    },
    'images': ['static/description/banner.png'],
    'application': True,
    'installable': True,
}
