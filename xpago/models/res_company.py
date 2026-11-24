from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    xpago_calculator_charge = fields.Boolean(
        string="The calculator also charges", default=True,
        help="Shows «Charge» under the result of the calculator, to charge it on an XPago terminal.")
    xpago_invoice_pay_qr = fields.Boolean(
        string="Pay link and QR on invoices",
        help="The PDF of an invoice not yet paid carries a QR and a link to pay it online with XPago.")
