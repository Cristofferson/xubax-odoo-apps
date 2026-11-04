{
    'name': 'XPago: Card Payments',
    'version': '20.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': 'Accept Visa, Mastercard and American Express in your online store, invoices and payment links, '
               'with months without interest by amount. Mexico.',
    'description': ' ',
    'author': 'XUBAX',
    'website': 'https://xpago.xubax.com',
    'support': 'hola@xubax.com',
    'license': 'OPL-1',
    'depends': ['payment'],
    'data': [
        'security/ir.access.csv',
        'views/payment_xpago_templates.xml',
        'views/payment_provider_views.xml',
        'data/payment_provider_data.xml',  # Before the methods: each method belongs to the provider.
        'data/payment_method_data.xml',
        'data/ir_cron.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'images': ['static/description/banner.png'],
    'installable': True,
}
