from odoo import _, api, models
from odoo.exceptions import AccessError, UserError


class PosPaymentMethod(models.Model):
    """«XPago transfer»: the sale is paid by SPEI to a CLABE made for it alone, shown on the register."""
    _inherit = 'pos.payment.method'

    def _get_terminal_provider_selection(self):
        return super()._get_terminal_provider_selection() + [('xpago_spei', "XPago transfer (one-time CLABE)")]

    @api.constrains('payment_provider', 'xpago_provider_id')
    def _check_xpago_transfer(self):
        for method in self.filtered(lambda m: m.payment_provider == 'xpago_spei'):
            if not method.xpago_provider_id:
                raise UserError(_("Choose the XPago account the transfers are paid to."))

    def _xpago_transfer_check_access(self):
        self.ensure_one()
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("Only point of sale users can charge by XPago transfer."))
        if self.payment_provider != 'xpago_spei':
            raise UserError(_("This payment method does not take XPago transfers."))
        provider = self.sudo().xpago_provider_id
        if not provider.active:
            raise UserError(_("XPago is disabled. An administrator can enable it in the XPago payment provider."))
        return provider

    def _xpago_transfer(self, transfer_id):
        transfer = self.env['pos.xpago.transfer'].sudo().browse(int(transfer_id)).exists()
        if not transfer or transfer.payment_method_id != self:
            raise UserError(_("This XPago transfer does not exist."))
        return transfer

    @api.model
    def _xpago_transfer_customer(self, data):
        """Who pays, as XPago wants it: name split in two, email and a phone with its country code (+52 by default)."""
        name = ' '.join((data.get('name') or '').split())
        first, _space, last = name.partition(' ')
        raw = (data.get('phone') or '').strip()
        digits = ''.join(char for char in raw if char.isdigit())
        if digits and not raw.startswith('+'):
            digits = '52' + digits[-10:] if len(digits) >= 10 else ''
        return {
            'first_name': first,
            'last_name': last or first,
            'email': (data.get('email') or '').strip(),
            'phone': '+' + digits if digits else '',
        }

    # Called by the point of sale

    def xpago_transfer_create(self, data):
        """Make the CLABE of this payment. ``data``: ``amount``, ``session_id``, ``order_uuid``, ``customer``
        (``name``, ``email``, ``phone``). Returns the transfer as the point of sale sees it."""
        provider = self._xpago_transfer_check_access()
        session = self.env['pos.session'].browse(data.get('session_id')).exists()
        account = self._xpago_charge_account(provider)
        transfer = self.env['pos.xpago.transfer'].sudo()._xpago_create(
            self.sudo(), provider, data.get('amount') or 0.0, session, data.get('order_uuid') or '',
            self._xpago_transfer_customer(data.get('customer') or {}), account=account)
        return transfer._xpago_public_view()

    def xpago_transfer_status(self, transfer_id):
        self._xpago_transfer_check_access()
        transfer = self._xpago_transfer(transfer_id)
        transfer._xpago_refresh()
        return transfer._xpago_public_view()

    def xpago_transfer_renew(self, transfer_id):
        """A new CLABE for the same sale, when the last one expired before the money arrived."""
        self._xpago_transfer_check_access()
        transfer = self._xpago_transfer(transfer_id)
        transfer._xpago_renew()
        return transfer._xpago_public_view()

    def xpago_transfer_cancel(self, transfer_id):
        self._xpago_transfer_check_access()
        transfer = self._xpago_transfer(transfer_id)
        transfer._xpago_cancel()
        return transfer._xpago_public_view()

    def xpago_transfer_force_check(self, data):
        """«Force done» on a transfer line: Odoo asks XPago first. The paid transfer of this sale for this amount
        that no payment of Odoo uses yet, else only its state (``none`` without a transfer)."""
        self._xpago_transfer_check_access()
        uuid = data.get('order_uuid') or ''
        transfers = self.env['pos.xpago.transfer'].sudo().search(
            [('payment_method_id', '=', self.id), ('order_uuid', '=', uuid)], order='id desc', limit=10) if uuid else None
        if not transfers:
            return {'state': 'none'}
        transfers._xpago_refresh()
        used = set(self.env['pos.payment'].sudo().search([
            ('payment_method_id', '=', self.id),
            ('transaction_id', 'in', [t.payment_id for t in transfers if t.payment_id]),
        ]).mapped('transaction_id'))
        currency = self.company_id.currency_id or self.env.company.currency_id
        for transfer in transfers:
            if transfer.state == 'paid' and transfer.payment_id not in used \
                    and not currency.compare_amounts(transfer.amount, data.get('amount') or 0.0):
                return transfer._xpago_public_view()
        state = transfers[0].state
        return {'state': 'unmatched' if state == 'paid' else state}
