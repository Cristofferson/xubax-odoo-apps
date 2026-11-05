{
    'name': 'XPago: Self-Order Kiosk',
    'version': '18.0.1.2.0',
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
            # The card voucher in the ticket the kiosk prints (the same receipt as the point of sale).
            'pos_xpago/static/src/app/order_receipt_voucher.js',
            'pos_xpago/static/src/app/order_receipt_voucher.xml',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
}
