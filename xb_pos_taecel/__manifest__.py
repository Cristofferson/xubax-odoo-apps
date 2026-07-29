# -*- coding: utf-8 -*-
{
    'name': 'POS Airtime & Bill Payments (TAECEL — Mexico)',
    'summary': 'Sell mobile airtime, data packages, bill payments and '
               'electronic PINs straight from the Point of Sale, through the '
               'TAECEL network: 30+ carriers, live balance and automatic '
               'reconciliation of interrupted sales.',
    'description': """
POS Airtime & Bill Payments (TAECEL)
====================================
Turn any Odoo Point of Sale into a top-up and bill-payment counter, connected
to the TAECEL network (Mexico).

Features
--------
* **Airtime and data packages** for 30+ Mexican carriers (Telcel, Movistar,
  AT&T, Unefon, Bait, Virgin, Weex and more) sold as ordinary POS lines.
* **Bill payments** with the customer service fee you configured, printed on
  the receipt as TAECEL requires.
* **Electronic PINs** delivered by SMS to the customer.
* **Two live wallets** — airtime and services are funded separately by TAECEL
  and are not transferable, so both are tracked and guarded independently. The
  cashier is warned before a sale that would overdraw one.
* **Never a lost sale**: a recharge that times out is parked, never re-sent,
  and settled automatically against TAECEL. No blind retries, no double
  recharge to the customer's phone.
* **Full audit trail**: every request, folio and authorization code kept
  against its POS order.
* Catalog synchronised from TAECEL on demand and on a schedule.

Requirements
------------
A TAECEL integrator account. TAECEL issues API credentials after approving the
"Levantamiento Tecnologico" (cc@taecel.com) and validating your test
transactions. A distributor account on its own does not include API access.

Runs on Odoo 18.0 and 19.0.
""",
    'category': 'Sales/Point of Sale',
    'version': '19.0.1.0.10',
    'author': 'Cristofferson Reyes',
    'website': 'https://xubax.com',
    'license': 'OPL-1',
    'price': 249.00,
    'currency': 'USD',
    'support': 'soporte@xubax.com',
    'depends': [
        'point_of_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
        'data/product_data.xml',
        'data/cron.xml',
        'views/xb_taecel_account_views.xml',
        'views/xb_taecel_product_views.xml',
        'views/xb_taecel_transaction_views.xml',
        'views/menus.xml',
        'report/taecel_deposit_templates.xml',
        'report/taecel_deposit_report.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'xb_pos_taecel/static/src/app/**/*.js',
            'xb_pos_taecel/static/src/app/**/*.xml',
            'xb_pos_taecel/static/src/app/**/*.scss',
        ],
    },
    'images': ['static/description/banner.png', 'static/description/icon.png'],
    'application': True,
    'installable': True,
}
