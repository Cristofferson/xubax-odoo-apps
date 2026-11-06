{
    'name': 'XPago: Point of Sale',
    'version': '19.0.2.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Installs by itself with XPago when you use the Odoo Point of Sale: the amount goes to the XPago card '
               'terminal and the approved card comes back to the order. Mexico.',
    'description': ' ',
    'author': 'XUBAX',
    'website': 'https://xpago.mx',
    'support': 'hola@xubax.com',
    'license': 'OPL-1',
    'depends': ['xpago', 'point_of_sale'],
    'auto_install': True,
    'data': [
        'security/ir.model.access.csv',
        'views/pos_payment_method_views.xml',
        'views/pos_xpago_charge_views.xml',
        'wizard/pos_xpago_reconcile_views.xml',
        'views/pos_payment_xpago_rule_views.xml',
        'views/res_config_settings_views.xml',
        'data/ir_cron.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'xpago_pos/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'xpago_pos/static/tests/unit/**/*',
        ],
    },
    'pre_init_hook': 'pre_init_hook',
    'images': ['static/description/banner.png'],
    'installable': True,
}
