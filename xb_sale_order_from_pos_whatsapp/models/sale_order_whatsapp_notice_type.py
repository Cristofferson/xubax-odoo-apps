# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS - WhatsApp add-on
from odoo import fields, models


class XbSaleOrderWhatsappNoticeType(models.Model):
    """The WhatsApp notices the seller can pick in the "Notify" window. Records rather
    than a selection: the window filters them per order with a domain, and the web
    client caches a field's selection per model, not per order."""

    _name = "xb.sale.order.whatsapp.notice.type"
    _description = "WhatsApp notice about an order"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, readonly=True, help="Key in sale.order.XB_WA_NOTICES.")
    sequence = fields.Integer(default=10)

    _code_unique = models.Constraint("UNIQUE(code)", "Each notice exists once.")
