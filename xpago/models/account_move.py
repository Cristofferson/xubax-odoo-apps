from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _xpago_pays_online(self):
        """The invoice's company takes online payments with XPago: its PDF shows XPago's QR and words (card or
        transfer) on Odoo's «pay online» QR, when that QR is turned on."""
        self.ensure_one()
        return bool(self.env['payment.provider'].sudo().search_count([
            ('code', '=', 'xpago'),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id),
        ], limit=1))
