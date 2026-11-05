{
    'name': 'XPago: Self-Order Kiosk',
    'version': '17.0.1.2.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Your customers order at the Odoo kiosk and pay on the XPago terminal beside it. Mexico.',
    'description': ' ',
    'author': 'XUBAX',
    'website': 'https://xpago.mx',
    'support': 'hola@xubax.com',
    'license': 'OPL-1',
    'depends': ['pos_xpago', 'pos_self_order'],
    'auto_install': True,
    'assets': {
        'pos_self_order.assets': [
            'pos_self_order_xpago/static/src/**/*',
            # The card voucher of the receipt, which the kiosk prints with the same template.
            'pos_xpago/static/src/app/order_receipt_voucher.xml',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
}
