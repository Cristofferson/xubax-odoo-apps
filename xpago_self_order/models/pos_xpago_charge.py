from datetime import timedelta

from odoo import api, fields, models


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
        config._notify('PAYMENT_STATUS', {
            'payment_result': payment_result,
            'data': {
                'pos.order': order.read(order._load_pos_self_data_fields(config.id), load=False),
                'pos.order.line': order.lines.read(order.lines._load_pos_self_data_fields(config.id), load=False),
                # The card of the payment, for the voucher of the ticket the kiosk prints.
                'pos.payment': order.payment_ids.read(order.payment_ids._load_pos_self_data_fields(config.id), load=False),
            },
        })

    @api.model
    def _xpago_cron_refresh(self):
        """The kiosk cancels its unpaid charge itself; this catches the kiosks that closed or lost their connection
        before, so their terminal does not stay waiting for a card."""
        self._xpago_cancel_abandoned_kiosk_charges()
        return super()._xpago_cron_refresh()

    @api.model
    def _xpago_cancel_abandoned_kiosk_charges(self):
        now = fields.Datetime.now()
        for charge in self.sudo().search([('state', '=', 'pending'), ('pos_order_id', '!=', False), ('config_id', '!=', False)]):
            timeout = charge.config_id.xpago_kiosk_timeout
            # A minute more than the kiosk's own timer: the kiosk normally cancels first.
            if timeout > 0 and charge.create_date <= now - timedelta(seconds=timeout + 60):
                charge._xpago_cancel()
