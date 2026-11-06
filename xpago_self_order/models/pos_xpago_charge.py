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
                order._send_payment_result('Success')
            elif charge.state in ('cancelled', 'expired') and order.state == 'draft':
                order._send_payment_result('fail')
