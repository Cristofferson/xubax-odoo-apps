# -*- coding: utf-8 -*-
from odoo import fields, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    xb_delivery_account_id = fields.Many2one(
        'xb.delivery.account', string='Delivery Account', copy=False,
        help='Payment method dedicated to a food delivery platform.')
