{
    'name': 'XPago: Self-Order Kiosk',
    'version': '19.0.1.2.0',
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
            # The card voucher in the kiosk's receipt, the same as at the register.
            'pos_xpago/static/src/app/order_receipt_voucher.js',
            'pos_xpago/static/src/app/order_receipt_voucher.xml',
            'pos_self_order_xpago/static/src/**/*',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
}
