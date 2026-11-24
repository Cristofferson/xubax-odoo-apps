# -*- coding: utf-8 -*-
{
    "name": "Sales, Quotations & Layaway from POS",
    "version": "17.0.1.4.0",
    "category": "Point of Sale",
    "summary": "Create quotations, sale orders and layaways (apartados) directly "
               "from the Point of Sale, with detailed receipt and balance.",
    "description": """
Sales, Quotations & Layaway from POS
====================================
Create a Quotation, a confirmed Sale Order or a Layaway (apartado) directly from
the POS screen, print a detailed receipt with the order lines, total and pending
balance, and let the customer finish online or be recovered in-store through the
native Odoo quotation/order flow.

All features are optional and configured per Point of Sale.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "company": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "license": "OPL-1",
    "depends": [
        "point_of_sale",
        "pos_sale",
        "sale",
        "sale_management",
        "portal",
        "base_automation",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/mail_template_data.xml",
        "data/mail_template_layaway.xml",
        "data/base_automation_layaway.xml",
        "data/ir_cron_data.xml",
        "views/res_config_settings_views.xml",
        "views/sale_order_views.xml",
        "views/sale_portal_templates.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "xb_sale_order_from_pos/static/src/app/**/*",
        ],
        "web.assets_tests": [
            "xb_sale_order_from_pos/static/tests/tours/**/*",
        ],
    },
    "images": [
        "static/description/banner.png",
    ],
    "price": 48.00,
    "currency": "USD",
    "installable": True,
    "application": False,
    "auto_install": False,
    # Packaging: heal pre-existing sale.order.amount_unpaid on install over existing
    # data (mirrors the _compute_amount_unpaid per-line fix). See __init__.py.
    "post_init_hook": "post_init_hook",
}
