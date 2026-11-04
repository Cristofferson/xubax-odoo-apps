from odoo import models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _payment_request_from_kiosk(self, order):
        """Send the order's amount to the terminal beside the kiosk. The charge pays the order by itself once the
        card is approved, and the kiosk hears it through its payment status channel."""
        if self.use_payment_terminal != 'xpago':
            return super()._payment_request_from_kiosk(order)
        provider = self.sudo().xpago_provider_id
        charge = self.env['pos.xpago.charge'].sudo()._xpago_create(
            self.sudo(), provider, order.amount_total, order.session_id, order.access_token or order.pos_reference or '', order=order)
        return {'xpago_charge_id': charge.id, 'state': charge.state}
