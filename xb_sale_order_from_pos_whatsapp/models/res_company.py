# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Per company: the "order ready" button shows only for companies that have one.
    xb_ready_wa_template_id = fields.Many2one(
        "whatsapp.template",
        string="Order ready WhatsApp template",
        domain=[("model", "=", "sale.order"), ("status", "=", "approved")],
        help="Approved WhatsApp template sent from the orders list (Sales and Point of "
             "Sale) to tell the customer the order is ready. Leave empty to hide the "
             "button for this company.",
    )
