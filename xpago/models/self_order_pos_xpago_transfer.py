from datetime import timedelta

from odoo import api, fields, models


class PosXpagoTransfer(models.Model):
    """A kiosk order paid by transfer: the CLABE is shown on the kiosk and the transfer pays the order by itself."""
    _inherit = 'pos.xpago.transfer'

    pos_order_id = fields.Many2one('pos.order', string="Kiosk order", readonly=True, ondelete='set null', index=True,
                                   help="Orders paid at a self-order kiosk, which the transfer itself completes.")

    def _xpago_on_state_changed(self):
        super()._xpago_on_state_changed()
        self._xpago_complete_kiosk_orders()

    def _xpago_complete_kiosk_orders(self):
        """The paid transfer becomes the payment of its kiosk order and the kiosk is told; a transfer that ended
        unpaid tells the kiosk it failed."""
        for transfer in self.filtered('pos_order_id'):
            order = transfer.pos_order_id.sudo()
            if order.state != 'draft':
                continue
            if transfer.state == 'paid':
                order.add_payment({
                    'amount': transfer.amount,
                    'payment_method_id': transfer.payment_method_id.id,
                    'pos_order_id': order.id,
                    'payment_status': 'done',
                    **transfer._xpago_payment_values(),
                })
                order.action_pos_order_paid()
                order._send_payment_result('Success')
            elif transfer.state in ('cancelled', 'returned', 'expired'):
                order._send_payment_result('fail')

    @api.model
    def _xpago_cron_refresh(self):
        """The kiosk cancels its unpaid transfer itself; this catches the kiosks that closed or lost their connection."""
        self._xpago_cancel_abandoned_kiosk_transfers()
        return super()._xpago_cron_refresh()

    @api.model
    def _xpago_cancel_abandoned_kiosk_transfers(self):
        now = fields.Datetime.now()
        for transfer in self.sudo().search([('state', 'in', ('awaiting', 'expired')), ('pos_order_id', '!=', False)]):
            timeout = transfer.pos_order_id.config_id.xpago_kiosk_transfer_timeout
            # A minute more than the kiosk's own timer: the kiosk normally cancels first.
            if timeout > 0 and transfer.create_date <= now - timedelta(seconds=timeout + 60):
                transfer._xpago_cancel()
                transfer._xpago_complete_kiosk_orders()
