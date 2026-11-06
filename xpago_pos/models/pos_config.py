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

    # The card voucher printed in the sale's own receipt (terminals that print with the point of sale, as the
    # N950 or the N750P, so the customer gets one ticket instead of two).
    xpago_voucher_on_receipt = fields.Boolean(
        string="Print the card voucher in the receipt", default=True,
        help="When the sale is paid with a card on an XPago terminal, the receipt (printed, emailed or sent by "
             "WhatsApp) carries the card details and the voucher legend.",
    )
    xpago_voucher_merchant = fields.Char(
        string="Merchant number",
        help="The affiliation number of the business, printed in the voucher. Optional.",
    )
    # The legends are Mexican law (the card network rules of a Mexican acquirer), so their default is Spanish.
    xpago_voucher_credit_text = fields.Text(
        string="Credit card legend",
        default=(
            'Por este pagaré me obligo incondicionalmente a pagar a la orden del banco emisor el importe de este '
            'título. Este pagaré procede del contrato de apertura de crédito que el banco emisor y el '
            'tarjetahabiente tienen celebrado. Pagaré negociable únicamente con instituciones de crédito.'),
    )
    xpago_voucher_debit_text = fields.Text(
        string="Debit card legend",
        default='Autorizo que se cargue a mi cuenta el importe de esta operación.',
    )
    xpago_voucher_signature = fields.Boolean(
        string="Signature line", default=True,
        help="Prints a line for the customer's signature under the legend.",
    )
