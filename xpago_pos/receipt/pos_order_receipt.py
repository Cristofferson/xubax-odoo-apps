from odoo import models


class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'

    def _order_receipt_generate_payment_data(self):
        """The card voucher of the XPago terminals (mirrored by payment_xpago_voucher.js for the receipt the point
        of sale prints)."""
        payments = super()._order_receipt_generate_payment_data()
        voucher = self.config_id.xpago_voucher_on_receipt
        payment_by_id = {payment.id: payment for payment in self.payment_ids}
        for data in payments:
            payment = payment_by_id.get(data['id'])
            card_type = (payment and payment.card_type or '').upper()
            data['xpago_voucher'] = bool(
                voucher and payment and payment.payment_method_id.payment_provider == 'xpago' and payment.amount > 0
                and (payment.card_no or payment.transaction_id))
            data['xpago_debit'] = 'DEBIT' in card_type
            data['xpago_credit'] = 'CREDIT' in card_type and 'DEBIT' not in card_type
        return payments
