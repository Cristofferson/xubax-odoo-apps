# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    # Reaches the POS with the rest of pos.config (it loads all its fields). The
    # quotation popup offers WhatsApp only when this is set, reading the raw id:
    # whatsapp.template itself is not loaded in the POS.
    xb_quotation_wa_template_id = fields.Many2one(
        "whatsapp.template",
        string="Quotation WhatsApp template",
        domain=[
            ("model", "=", "sale.order"),
            ("status", "=", "approved"),
            ("header_type", "=", "image"),
        ],
        help="Approved WhatsApp template used when the cashier sends a quotation by "
             "WhatsApp. Its header must be an image: the ticket goes there, the same "
             "one that is printed. Leave empty to not offer WhatsApp at this Point of "
             "Sale.",
    )
