import base64

from odoo import models
from odoo.tools.image import image_data_uri


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _xpago_pays_online(self):
        """The invoice's company takes online payments with XPago."""
        self.ensure_one()
        return bool(self.env['payment.provider'].sudo().search_count([
            ('code', '=', 'xpago'),
            ('state', 'in', ('enabled', 'test')),
            ('company_id', '=', self.company_id.id),
        ], limit=1))

    def _xpago_show_pay_qr(self):
        """The PDF carries XPago's pay link and QR: turned on in the settings, a customer invoice with something left
        to pay, and a company that takes online payments with XPago. (Odoo 19 has this QR of its own; 17 and 18 not.)"""
        self.ensure_one()
        return bool(self.company_id.xpago_invoice_pay_qr and self.move_type in ('out_invoice', 'out_receipt')
                    and self.state == 'posted' and self.amount_residual and self._xpago_pays_online())

    def _xpago_pay_link(self):
        """The link to pay what is left of the invoice online (Odoo's payment link, with its access token)."""
        self.ensure_one()
        wizard = self.env['payment.link.wizard'].sudo().with_context(
            active_id=self.id, active_model=self._name).create({
                'amount': self.amount_residual, 'res_model': self._name, 'res_id': self.id})
        return wizard.link

    def _xpago_pay_qr(self, link):
        barcode = self.env['ir.actions.report'].barcode(barcode_type='QR', value=link, width=128, height=128,
                                                        quiet=False)
        return image_data_uri(base64.b64encode(barcode))
