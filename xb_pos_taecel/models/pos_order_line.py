# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosOrderLine(models.Model):
    """Carries the TAECEL metadata a recharge line needs to be dispatched.

    An airtime/service sale is an ordinary POS line on a generic service
    product; what makes it a TAECEL sale is this metadata, captured in the POS
    and rounded back to the server so the order can create its transaction.
    """
    _inherit = 'pos.order.line'

    taecel_is_taecel = fields.Boolean(string='Recharge Line', copy=False)
    taecel_carrier_id = fields.Many2one(
        'xb.taecel.carrier', string='Carrier', copy=False, ondelete='restrict')
    taecel_product_code = fields.Char(string='Product Code', copy=False)
    taecel_reference = fields.Char(
        string='Recharge Reference', copy=False,
        help='Phone number or bill reference the recharge is dispatched to.')
    taecel_bolsa_id = fields.Char(string='Wallet', copy=False)
    taecel_fee = fields.Monetary(string='Customer Fee', copy=False)
    taecel_transaction_ids = fields.One2many(
        'xb.taecel.transaction', 'pos_order_line_id', copy=False)

    @api.model
    def _load_pos_data_fields(self, config=None):
        # ``config=None`` so both the Odoo 18 (id) and 19 (recordset) call
        # arities bind; see models/pos_compat.py.
        fields_ = super()._load_pos_data_fields(config)
        if fields_:
            fields_ += [
                'taecel_is_taecel', 'taecel_carrier_id', 'taecel_product_code',
                'taecel_reference', 'taecel_bolsa_id', 'taecel_fee',
            ]
        return fields_
