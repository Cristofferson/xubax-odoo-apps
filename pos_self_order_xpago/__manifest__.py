{
    'name': 'XPago: Self-Order Kiosk',
    'version': '20.0.1.1.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Your customers order at the Odoo kiosk and pay on the XPago terminal beside it. Mexico.',
    'description': ' ',
    'author': 'XUBAX',
    'website': 'https://xpago.xubax.com',
    'support': 'hola@xubax.com',
    'license': 'OPL-1',
    'depends': ['pos_xpago', 'pos_self_order'],
    'auto_install': True,
    'assets': {
        'pos_self_order.assets': [
            'pos_self_order_xpago/static/src/**/*',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
}
