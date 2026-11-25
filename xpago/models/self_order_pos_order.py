from odoo import models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _export_for_self_order(self):
        """The card voucher of the XPago payments, for the ticket the kiosk prints."""
        result = super()._export_for_self_order()
        for line, payment in zip(result.get('payment_lines') or [], self.payment_ids):
            line['xpago_voucher'] = payment._xpago_voucher()
        return result

    def _xpago_send_payment_result(self, payment_result):
        """Tell the kiosk how the payment of this order ended, on the channel it listens to while the customer pays
        (Odoo 17 has no ``_send_payment_result``)."""
        self.ensure_one()
        config = self.config_id
        if config.self_ordering_mode != 'kiosk':
            return
        self.env['bus.bus']._sendone(f'pos_config-{config.access_token}', 'PAYMENT_STATUS', {
            'payment_result': payment_result,
            'order': self._export_for_self_order(),
        })
