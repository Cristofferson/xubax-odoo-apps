from odoo import models


class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'

    def _order_receipt_generate_payment_data(self):
        """The card voucher of the XPago terminals and the CLABE of the XPago transfers (mirrored by
        payment_xpago_voucher.js for the receipt the point of sale prints)."""
        payments = super()._order_receipt_generate_payment_data()
        # On the terminal's own printer the terminal adds its certified voucher under this receipt.
        voucher = self.config_id.xpago_voucher_on_receipt and not self.config_id.xpago_print_on_terminal
        payment_by_id = {payment.id: payment for payment in self.payment_ids}
        for data in payments:
            payment = payment_by_id.get(data['id'])
            card_type = (payment and payment.card_type or '').upper()
            data['xpago_voucher'] = bool(
                voucher and payment and payment.payment_method_id.payment_provider == 'xpago' and payment.amount != 0
                and (payment.card_no or payment.transaction_id))
            data['xpago_terms'] = payment.xpago_terms if payment and payment.xpago_terms > 1 else 0
            data['xpago_debit'] = 'DEBIT' in card_type
            data['xpago_credit'] = 'CREDIT' in card_type and 'DEBIT' not in card_type
            data['xpago_transfer'] = bool(
                payment and payment.payment_method_id.payment_provider == 'xpago_spei' and payment.amount != 0
                and (payment.card_no or payment.transaction_id))
            # A refund paid back to the card or by transfer: the customer keeps the proof of where the money goes.
            data['xpago_refund'] = bool(payment and payment.amount < 0)
            if data['xpago_refund']:
                currency = payment.foreign_currency_id or self.currency_id
                data['xpago_amount'] = self._order_receipt_format_currency(abs(payment.amount_currency or payment.amount), currency)
            else:
                data['xpago_amount'] = data['amount']
            # Chip and contactless are verified by PIN or need nothing: only a swiped or keyed card is signed, and
            # nothing is signed when the money goes back to the customer.
            data['xpago_signature'] = bool(
                not data['xpago_refund'] and self.config_id.xpago_voucher_signature
                and (payment and payment.payment_method_payment_mode or '').upper() not in ('CHIP', 'CONTACTLESS'))
        return payments
