from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    xpago_calculator_charge = fields.Boolean(
        string="The calculator also charges", default=True,
        help="Shows «Charge» under the result of the calculator, to charge it on an XPago terminal.")
