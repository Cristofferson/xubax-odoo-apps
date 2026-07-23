# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductSupplierinfo(models.Model):
    _inherit = 'product.supplierinfo'

    xb_vbp_cost_synced = fields.Boolean(
        string="Cost taken from a bill",
        copy=False,
        help="Set the first time a vendor bill wrote the price on this line. "
             "The \"only the first time\" cost policy relies on it.",
    )
    xb_vbp_last_move_id = fields.Many2one(
        comodel_name='account.move',
        string="Last bill read",
        copy=False,
        ondelete='set null',
    )
