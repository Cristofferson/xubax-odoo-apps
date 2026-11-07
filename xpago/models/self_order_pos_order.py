from odoo import models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _export_for_self_order(self):
        """The card voucher of the XPago payments, for the ticket the kiosk prints."""
        result = super()._export_for_self_order()
        for line, payment in zip(result.get('payment_lines') or [], self.payment_ids):
            line['xpago_voucher'] = payment._xpago_voucher()
        return result
