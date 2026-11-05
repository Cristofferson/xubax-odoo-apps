from odoo import models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _notify(self, *notifications, private=True):
        """The kiosk prints the card voucher of an XPago payment in its receipt: the card goes with the payment status
        of the order it paid."""
        if len(notifications) == 2 and notifications[0] == 'PAYMENT_STATUS':
            message = notifications[1]
            data = message.get('data') or {}
            if message.get('payment_result') == 'Success' and data.get('pos.order') and 'pos.payment' not in data:
                Payment = self.env['pos.payment'].sudo()
                payments = Payment.browse(data['pos.order'][0].get('payment_ids') or []).exists().filtered(
                    lambda p: p.payment_method_id.use_payment_terminal == 'xpago')
                if payments:
                    notifications = ('PAYMENT_STATUS', {
                        **message, 'data': {**data, 'pos.payment': Payment._load_pos_self_data_read(payments, self)}})
        return super()._notify(*notifications, private=private)
