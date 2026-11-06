{
    'name': 'XPago: Card Payments and Terminals',
    'version': '18.0.2.0.0',
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': 'Accept Visa, Mastercard and American Express in Mexico: online store, invoices, payment links and '
               'subscriptions, and card terminals in the Point of Sale and the kiosk, with months without interest and '
               'deposit accounts by product.',
    'description': ' ',
    'author': 'XUBAX',
    'website': 'https://xpago.mx',
    'support': 'hola@xubax.com',
    'license': 'OPL-1',
    'depends': ['payment', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_xpago_templates.xml',
        'views/payment_xpago_rule_views.xml',
        'views/payment_provider_views.xml',
        'data/payment_provider_data.xml',
        'data/ir_cron.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
}
