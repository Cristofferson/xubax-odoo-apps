# -*- coding: utf-8 -*-
"""1.4.0: the layaway / balance reminders join the automatic messages. Each company that
already has its approved «balance due» template gets both, OFF, with that template: the
shop switches them on (Sales › Configuration › Automatic WhatsApp messages)."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Automation = env["xb.sale.order.wa.automation"]
    for company in env["res.company"].search([("xb_payment_wa_template_id.status", "=", "approved")]):
        Automation._xb_ensure(company)
        Automation.search([
            ("company_id", "=", company.id), ("kind", "in", ("layaway_due", "order_due")),
            ("template_id", "=", False),
        ]).write({"template_id": company.xb_payment_wa_template_id.id})
