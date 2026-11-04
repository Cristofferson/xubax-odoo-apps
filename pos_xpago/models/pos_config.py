from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    xpago_show_account = fields.Boolean(
        string="Show the deposit account to the cashier", default=True,
        help="Before charging on an XPago terminal, the cashier sees which account the money goes to (and in how "
             "many parts, when the sale is split).",
    )
    xpago_split = fields.Boolean(
        string="Split the charge by account and months",
        help="When the products of a sale go to different accounts or allow different months without interest "
             "(XPago payment rules), the charge is split: one charge per account, each with its months.",
    )
