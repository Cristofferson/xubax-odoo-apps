{
    'name': 'XPago: Card Payments and Terminals',
    'version': '19.0.2.0.0',
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': 'Accept Visa, Mastercard and American Express in Mexico: card terminals in the Point of Sale, online '
               'store, invoices, payment links and subscriptions, with months without interest and deposit accounts '
               'by product.',
    'description': ' ',
    'author': 'XUBAX',
    'website': 'https://xpago.mx',
    'support': 'hola@xubax.com',
    'license': 'OPL-1',
    'depends': ['payment', 'product', 'point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_xpago_templates.xml',
        'views/payment_xpago_rule_views.xml',
        'views/payment_provider_views.xml',
        'data/payment_provider_data.xml',
        'data/ir_cron.xml',
        'views/pos_payment_method_views.xml',
        'views/pos_xpago_charge_views.xml',
        'wizard/pos_xpago_reconcile_views.xml',
        'views/pos_payment_xpago_rule_views.xml',
        'views/res_config_settings_views.xml',
        'data/ir_cron_pos.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'xpago/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'xpago/static/tests/unit/**/*',
        ],
    },
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
}
