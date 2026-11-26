from odoo import models


# Below this amount the processor does not offer SPEI transfer, only card.
XPAGO_SPEI_MIN_AMOUNT = 200


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

    def _xpago_invoice_offers_transfer(self):
        """The online payment of this invoice offers SPEI transfer, so its PDF may say so: XPago offers bank transfer
        for the invoice's company and what is left to pay reaches the processor's minimum. Otherwise, card only."""
        self.ensure_one()
        return bool(self.amount_residual >= XPAGO_SPEI_MIN_AMOUNT and self.env['payment.provider'].sudo().search_count([
            ('code', '=', 'xpago'),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id),
            ('xpago_offer_bank_transfer', '=', True),
        ], limit=1))
