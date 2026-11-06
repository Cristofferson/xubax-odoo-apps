{
    'name': 'XPago: Self-Order Kiosk',
    'version': '18.0.2.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Installs by itself with XPago when you use the Odoo kiosk: your customers order at the kiosk and '
               'pay on the XPago terminal beside it. Mexico.',
    'description': ' ',
    'author': 'XUBAX',
    'website': 'https://xpago.mx',
    'support': 'hola@xubax.com',
    'license': 'OPL-1',
    'depends': ['xpago_pos', 'pos_self_order'],
    'auto_install': True,
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'pos_self_order.assets': [
            # The same waiting as the register: often at first, less after, once more at expiry.
            'xpago_pos/static/src/app/charge_wait.js',
            'xpago_self_order/static/src/**/*',
            # The card voucher in the ticket the kiosk prints (the same receipt as the point of sale).
            'xpago_pos/static/src/app/order_receipt_voucher.js',
            'xpago_pos/static/src/app/order_receipt_voucher.xml',
        ],
    },
    'pre_init_hook': 'pre_init_hook',
    'images': ['static/description/banner.png'],
    'installable': True,
}
