# -*- coding: utf-8 -*-
{
    "name": "Sales, Quotations & Layaway from POS - CFDI 4.0 (Mexico)",
    "summary": "SAT «Forma de pago» on the POS payment methods, reported on the CFDI "
               "of the orders created with Sales, Quotations & Layaway from POS.",
    "description": """
Sales, Quotations & Layaway from POS - CFDI 4.0
===============================================
Map each POS payment method to the SAT «Forma de pago» (01 Efectivo,
03 Transferencia, 04 Tarjeta de crédito, 28 Tarjeta de débito...): when an order
created with *Sales, Quotations & Layaway from POS* is invoiced, the CFDI reports how
it was actually paid.

Installs itself as soon as both *Sales, Quotations & Layaway from POS* and Odoo's
Mexican localisation (``l10n_mx_edi``) are present.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Accounting/Localizations",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": [
        "xb_sale_order_from_pos",
        "l10n_mx_edi",
    ],
    "data": [
        "views/pos_payment_method_views.xml",
    ],
    "images": [
        "static/description/icon.png",
    ],
    "application": False,
    "installable": True,
    "auto_install": True,
}
