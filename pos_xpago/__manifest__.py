{
    'name': 'XPago: Card Terminals in the Point of Sale',
    'version': '18.0.1.2.0',
    'category': 'Sales/Point of Sale',
    'sequence': 6,
    'summary': 'Charge on XPago card terminals from the Odoo Point of Sale: the amount goes to the terminal and the '
               'approved card comes back to the order. Mexico.',
    'description': ' ',
    'author': 'XUBAX',
    'website': 'https://xpago.mx',
    'support': 'hola@xubax.com',
    'license': 'OPL-1',
    'depends': ['point_of_sale', 'payment_xpago'],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_payment_method_views.xml',
        'views/pos_xpago_charge_views.xml',
        'wizard/pos_xpago_reconcile_views.xml',
        'views/payment_xpago_rule_views.xml',
        'views/res_config_settings_views.xml',
        'data/ir_cron.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_xpago/static/src/**/*',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
}
