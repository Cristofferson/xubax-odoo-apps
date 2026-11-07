from odoo import _, fields, models

# The card of an XPago payment, as the voucher of the receipt prints it. Odoo 17 keeps only the card type and
# the transaction id on the payment.
XPAGO_CARD_FIELDS = (
    'xpago_card_brand', 'xpago_card_no', 'xpago_issuer_bank', 'xpago_authorization', 'xpago_reference',
    'xpago_entry_mode', 'xpago_terms', 'xpago_tip',
)


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    xpago_card_brand = fields.Char(string="Card brand", readonly=True)
    xpago_card_no = fields.Char(string="Card (last 4)", readonly=True)
    xpago_issuer_bank = fields.Char(string="Bank", readonly=True)
    xpago_authorization = fields.Char(string="Authorization", readonly=True)
    xpago_reference = fields.Char(string="Reference", readonly=True)
    xpago_entry_mode = fields.Char(string="Entry mode", readonly=True)
    xpago_terms = fields.Integer(string="Months without interest", readonly=True)
    xpago_tip = fields.Monetary(string="Tip", readonly=True)

    def _export_for_ui(self, payment):
        result = super()._export_for_ui(payment)
        result.update({name: payment[name] for name in XPAGO_CARD_FIELDS})
        return result

    def _xpago_voucher(self):
        """The card voucher this payment prints in the receipt, as the point of sale builds it (see
        order_receipt_voucher.js), for receipts rendered from the server's data (self-order kiosk). False: only
        positive card payments of XPago terminals."""
        self.ensure_one()
        config = self.pos_order_id.config_id
        if not config.xpago_voucher_on_receipt or self.payment_method_id.use_payment_terminal != 'xpago' \
                or self.amount <= 0 or not (self.xpago_card_no or self.xpago_authorization):
            return False
        # Odoo 17 keeps the brand and the funding of the card together in its type ("VISA CREDIT").
        card_type = (self.card_type or '').upper()
        debit = 'DEBIT' in card_type
        return {
            'brand': self.xpago_card_brand or '',
            'card_no': self.xpago_card_no or '',
            'funding': _("Debit") if debit else _("Credit") if 'CREDIT' in card_type else '',
            'bank': self.xpago_issuer_bank or '',
            'authorization': self.xpago_authorization or '',
            # The operation the processor gave; its internal id (transaction_id) stays out of the ticket.
            'operation': self.xpago_reference or '',
            'entry_mode': self.xpago_entry_mode or '',
            'merchant': config.xpago_voucher_merchant or '',
            'terms': self.xpago_terms if self.xpago_terms > 1 else False,
            'tip': self.xpago_tip or 0.0,
            'legend': (config.xpago_voucher_debit_text if debit else config.xpago_voucher_credit_text) or '',
            # Chip and contactless are verified by PIN or need nothing: only a swiped or keyed card is signed.
            'signature': bool(config.xpago_voucher_signature)
                         and (self.xpago_entry_mode or '').upper() not in ('CHIP', 'CONTACTLESS'),
        }
