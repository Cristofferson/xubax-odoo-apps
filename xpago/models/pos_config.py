from odoo import api, fields, models


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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('xpago_tip_mode') in ('terminal', 'cashier'):
                vals['iface_tipproduct'] = True
        return super().create(vals_list)

    def write(self, vals):
        # A tip needs Odoo's tip product: turned on with the tip mode, so the tip lands on its own line.
        if vals.get('xpago_tip_mode') in ('terminal', 'cashier'):
            vals = {**vals, 'iface_tipproduct': True}
        return super().write(vals)

    # Odoo open on the terminal itself, printing on the terminal's printer (the processor's POS app answers as an Epson
    # ePOS printer on 127.0.0.1:8008). The terminal then prints its certified card voucher right under Odoo's receipt.
    xpago_print_on_terminal = fields.Boolean(
        string="Odoo prints on the XPago terminal",
        help="This point of sale runs on the XPago terminal and prints Odoo's receipt on the terminal's printer "
             "(Epson printer at 127.0.0.1:8008). The terminal prints the card voucher right under the receipt, on "
             "the same paper, instead of on its own; Odoo then leaves the voucher out of its receipt.",
    )

    xpago_tip_mode = fields.Selection(
        [('none', "No tip"), ('terminal', "The terminal asks the customer"), ('cashier', "The cashier enters it")],
        string="XPago tip", default='none', required=True,
        help="No tip: nothing changes. The terminal asks: on every card charge the terminal shows the customer its "
             "tip screen (10, 15, 20%, another amount or none), unless the cashier already added a tip in Odoo; the "
             "processor must have tips turned on for the business. The cashier enters it: with Odoo's «Tip» button "
             "on the payment screen; the terminal charges sale and tip together without asking. In both cases the "
             "tip is a line of the order, so the closing matches what the terminal charged.",
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
