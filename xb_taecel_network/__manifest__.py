# -*- coding: utf-8 -*-
{
    'name': 'TAECEL Distributor Network (Mexico)',
    'summary': 'Watch the balance, sales and margin of every affiliate in your '
               'TAECEL distributor network from Odoo, and hand each one the '
               'bank reference that funds it.',
    'description': """
TAECEL Distributor Network
==========================
For TAECEL **distributors**: a single screen for the affiliates you registered
in MI RED, instead of logging into the portal one account at a time.

What it does
------------
* **Live balance per affiliate**, wallet by wallet (airtime, bill payments,
  CFDI stamps), read straight from TAECEL.
* **Sales pulled per affiliate**, with folio, carrier, status and the
  commission TAECEL paid on each one.
* **Your margin**, which is the whole point of a network: the difference
  between the commission TAECEL grants you and the one you granted the
  affiliate, applied to what it actually sold.
* **Deposit reference per affiliate** -- depositing against it credits that
  affiliate automatically, so you stop transferring balance by hand.

Requirements
------------
A TAECEL distributor account with API credentials, plus the WS credentials of
each affiliate you want to watch (TAECEL issues them to the affiliate when you
register it in MI RED).

What it does NOT do
-------------------
TAECEL's web service has no method to transfer balance, suspend an affiliate,
change its commission or list your network: those live only in the MI RED
portal. This module reads what the API does expose and computes the rest; it
does not pretend to replace the portal.

Runs on Odoo 18.0 and 19.0.
""",
    'category': 'Sales/Point of Sale',
    'version': '19.0.1.0.3',
    'author': 'Cristofferson Reyes',
    'website': 'https://xubax.com',
    'license': 'OPL-1',
    'price': 149.00,
    'currency': 'USD',
    'support': 'soporte@xubax.com',
    'depends': [
        'xb_pos_taecel',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
        'data/cron.xml',
        'views/xb_taecel_affiliate_views.xml',
        'views/xb_taecel_affiliate_sale_views.xml',
        'views/menus.xml',
        'report/taecel_affiliate_deposit_report.xml',
    ],
    # No 'images' yet: banner.png / icon.png are still to be produced, and
    # pointing the manifest at files that do not exist breaks the store zip.
    'installable': True,
    'application': False,
}
