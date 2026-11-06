from odoo import models


class PosXpagoCharge(models.Model):
    _inherit = 'pos.xpago.charge'

    def _xpago_complete_orders(self):
        """A kiosk order is paid by its charge: the approved card becomes its payment and the kiosk is told."""
        super()._xpago_complete_orders()
        for charge in self.filtered('pos_order_id'):
            order = charge.pos_order_id.sudo()
            if charge.state == 'confirmed' and order.state == 'draft':
                order.add_payment({
                    'amount': charge.amount,
                    'payment_method_id': charge.payment_method_id.id,
                    'pos_order_id': order.id,
                    'payment_status': 'done',
                    **charge._xpago_payment_values(),
                })
                order.action_pos_order_paid()
                order._send_order()
                charge._xpago_notify_kiosk(order, 'Success')
            elif charge.state in ('cancelled', 'expired') and order.state == 'draft':
                charge._xpago_notify_kiosk(order, 'fail')

    def _xpago_notify_kiosk(self, order, payment_result):
        """Tell the kiosk how the payment ended, on the channel it listens to while the customer pays."""
        config = order.config_id
        if config.self_ordering_mode != 'kiosk':
            return
        self.env['bus.bus']._sendone(f'pos_config-{config.access_token}', 'PAYMENT_STATUS', {
            'payment_result': payment_result,
            'order': order._export_for_self_order(),
        })
