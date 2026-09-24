# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Per company: each notice is offered only by companies that have its template.
    xb_ready_wa_template_id = fields.Many2one(
        "whatsapp.template",
        string="Order ready WhatsApp template",
        domain=[("model", "=", "sale.order"), ("status", "=", "approved")],
        help="Approved WhatsApp template sent from the orders list (Sales and Point of "
             "Sale) to tell the customer the order is ready. Leave empty to not offer "
             "this notice for this company.",
    )
    xb_delay_wa_template_id = fields.Many2one(
        "whatsapp.template",
        string="Order late WhatsApp template",
        domain=[("model", "=", "sale.order"), ("status", "=", "approved")],
        help="Approved WhatsApp template sent from the orders list (Sales and Point of "
             "Sale) to apologise for a late order and give the customer the new delivery "
             "date. Leave empty to not offer this notice for this company.",
    )
    xb_payment_wa_template_id = fields.Many2one(
        "whatsapp.template",
        string="Balance due reminder WhatsApp template",
        domain=[("model", "=", "sale.order"), ("status", "=", "approved")],
        help="Approved WhatsApp template sent from the orders list (Sales and Point of "
             "Sale) to remind the customer of the balance still due on an order or "
             "layaway. Leave empty to not offer this notice for this company.",
    )
    xb_pickup_wa_template_id = fields.Many2one(
        "whatsapp.template",
        string="Pick-up reminder WhatsApp template",
        domain=[("model", "=", "sale.order"), ("status", "=", "approved")],
        help="Approved WhatsApp template sent from the orders list (Sales and Point of "
             "Sale) to remind the customer that a ready order is waiting to be picked "
             "up. Leave empty to not offer this notice for this company.",
    )
    xb_detail_wa_template_id = fields.Many2one(
        "whatsapp.template",
        string="Confirm a detail WhatsApp template",
        domain=[("model", "=", "sale.order"), ("status", "=", "approved")],
        help="Approved WhatsApp template sent from the orders list (Sales and Point of "
             "Sale) to ask the customer to reply and confirm a detail of the order (size, "
             "engraving, stone...). It opens the conversation: once the customer answers, "
             "the seller can write freely. Leave empty to not offer this notice for this "
             "company.",
    )
