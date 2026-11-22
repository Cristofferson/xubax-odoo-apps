from odoo import fields, models


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    xpago_terms = fields.Integer(
        string="Months without interest", readonly=True,
        help="The months without interest of this XPago card payment (0 or 1: single payment). Printed on the voucher.",
    )
