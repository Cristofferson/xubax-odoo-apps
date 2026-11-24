from odoo import _, api, models
from odoo.exceptions import AccessError, UserError


class PosPaymentMethod(models.Model):
    """«XPago transfer»: the sale is paid by SPEI to a CLABE made for it alone, shown on the register."""
    _inherit = 'pos.payment.method'

    def _get_payment_terminal_selection(self):
        return super()._get_payment_terminal_selection() + [('xpago_spei', "XPago transfer (one-time CLABE)")]

    @api.constrains('use_payment_terminal', 'xpago_provider_id')
    def _check_xpago_transfer(self):
        for method in self.filtered(lambda m: m.use_payment_terminal == 'xpago_spei'):
            if not method.xpago_provider_id:
                raise UserError(_("Choose the XPago account the transfers are paid to."))

    def _xpago_transfer_check_access(self):
        self.ensure_one()
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("Only point of sale users can charge by XPago transfer."))
        if self.use_payment_terminal != 'xpago_spei':
            raise UserError(_("This payment method does not take XPago transfers."))
        provider = self.sudo().xpago_provider_id
        if provider.state == 'disabled':
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
            'display_name': name,  # as the customer is called; XPago needs a last name, so a single name is sent twice
            'first_name': first,
            'last_name': last or first,
            'email': (data.get('email') or '').strip(),
            'phone': '+' + digits if digits else '',
        }

    # Called by the point of sale

    def xpago_transfer_create(self, data):
        """Make the CLABE of this payment. ``data``: ``amount``, ``session_id``, ``order_uuid``, ``customer``
        (``name``, ``email``, ``phone``) and ``rule_account_id`` (the account of the payment rules). Returns the transfer
        as the point of sale sees it."""
        provider = self._xpago_transfer_check_access()
        session = self.env['pos.session'].browse(data.get('session_id')).exists()
        uuid = data.get('order_uuid') or ''
        amount = data.get('amount') or 0.0
        # The transfers of this sale still open are asked to XPago first: money that arrived while nobody looked pays
        # the sale, and a CLABE still waiting for this amount is shown again instead of a second one (the customer
        # may be paying it right now).
        open_transfers = self.env['pos.xpago.transfer'].sudo().search(
            [('payment_method_id', '=', self.id), ('order_uuid', '=', uuid), ('state', '=', 'awaiting')],
            order='id desc', limit=10) if uuid else self.env['pos.xpago.transfer']
        open_transfers._xpago_refresh()
        taken = data.get('taken_payment_ids')
        paid = self._xpago_transfer_paid_unused(uuid, amount, taken=taken)
        if paid:
            # «Retry» after the register gave up on a transfer that arrived after all: that one pays the sale.
            return paid._xpago_public_view()
        currency = self.company_id.currency_id or self.env.company.currency_id
        # A CLABE another payment line of this sale is waiting on belongs to that line (two transfers of the same
        # amount are two CLABEs).
        followed = {int(i) for i in data.get('followed_transfer_ids') or [] if isinstance(i, int)}
        waiting = open_transfers.filtered(
            lambda t: t.state == 'awaiting' and t.id not in followed
            and not currency.compare_amounts(t.amount, amount))[:1]
        if waiting:
            return waiting._xpago_public_view()
        account = self._xpago_charge_account(provider, rule_account_id=data.get('rule_account_id'))
        transfer = self.env['pos.xpago.transfer'].sudo()._xpago_create(
            self.sudo(), provider, data.get('amount') or 0.0, session, data.get('order_uuid') or '',
            self._xpago_transfer_customer(data.get('customer') or {}), account=account)
        return transfer._xpago_public_view()

    def xpago_transfer_refund(self, data):
        """A refund order paid back with «Transfer»: the paid transfer of the original sale for that amount goes back
        to who paid. XPago refunds a transfer in full and the same day only."""
        self._xpago_transfer_check_access()
        amount = -(data.get('amount') or 0.0)
        if amount <= 0:
            raise UserError(_("A refund is paid back with a negative amount."))
        orders = self.env['pos.order'].browse(data.get('refunded_order_ids') or []).exists()
        payments = orders.sudo().payment_ids.filtered(lambda p: p.payment_method_id == self and p.transaction_id)
        # Odoo 17: the register knows a sale by its uid, kept in the order's reference («Order 00001-001-0001»).
        uids = [ref.split(' ', 1)[-1] for ref in orders.mapped('pos_reference') if ref]
        transfers = self.env['pos.xpago.transfer'].sudo().search([
            ('payment_method_id', '=', self.id), ('state', '=', 'paid'), '|',
            ('payment_id', 'in', payments.mapped('transaction_id')), ('order_uuid', 'in', uids)])
        currency = self.company_id.currency_id or self.env.company.currency_id
        transfer = transfers.filtered(lambda t: not currency.compare_amounts(t.amount, amount))[:1]
        if not transfer:
            if transfers:
                raise UserError(_(
                    "XPago gives back a transfer in full only. Refund %(amounts)s, or pay this refund in cash.",
                    amounts=", ".join(currency.format(t.amount) for t in transfers)))
            raise UserError(_("No transfer of this method was found in the original sale. Pay this refund in cash."))
        transfer._xpago_refund()
        return {'state': transfer.state, 'payment': transfer._xpago_payment_values()}

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

    def _xpago_transfer_paid_unused(self, uuid, amount, transfers=None, taken=None):
        """The paid transfer of this sale for this amount that no payment of Odoo uses yet. ``taken``: the payment ids
        the other lines of the sale on the register already hold."""
        if transfers is None:
            transfers = self.env['pos.xpago.transfer'].sudo().search(
                [('payment_method_id', '=', self.id), ('order_uuid', '=', uuid), ('state', '=', 'paid')],
                order='id desc', limit=10) if uuid else self.env['pos.xpago.transfer']
        if not transfers:
            return transfers
        used = set(self.env['pos.payment'].sudo().search([
            ('payment_method_id', '=', self.id),
            ('transaction_id', 'in', [t.payment_id for t in transfers if t.payment_id]),
        ]).mapped('transaction_id')) | {t for t in taken or [] if isinstance(t, str) and t}
        currency = self.company_id.currency_id or self.env.company.currency_id
        for transfer in transfers:
            if transfer.state == 'paid' and (not transfer.payment_id or transfer.payment_id not in used) \
                    and not currency.compare_amounts(transfer.amount, amount):
                return transfer
        return transfers.browse()

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
        paid = self._xpago_transfer_paid_unused(uuid, data.get('amount') or 0.0, transfers,
                                                taken=data.get('taken_payment_ids'))
        if paid:
            return paid._xpago_public_view()
        state = transfers[0].state
        return {'state': 'unmatched' if state == 'paid' else state}
