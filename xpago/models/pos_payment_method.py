from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    xpago_provider_id = fields.Many2one(
        'payment.provider', string="XPago account", domain="[('code', '=', 'xpago')]",
        default=lambda self: self.env['payment.provider'].search(
            [('code', '=', 'xpago'), ('company_id', 'in', self.env.company.parent_ids.ids)], order='company_id desc', limit=1),
        help="The XPago account this terminal charges with: its XPago key and whether it is in test mode.",
    )
    xpago_terminal_serial = fields.Char(
        string="Terminal S/N", help="The serial number on the back of the terminal (after S/N).",
    )
    xpago_open_terminal_app = fields.Boolean(
        string="Odoo runs on this terminal",
        help="Bring the charge app to the front when the point of sale runs on the terminal itself.",
    )

    xpago_bank_account_id = fields.Many2one(
        'payment.xpago.bank.account', string="Deposit account", domain="[('provider_id', '=', xpago_provider_id)]",
        help="Where XPago deposits what this terminal charges. Empty: your XPago account decides.",
    )
    xpago_choose_account = fields.Boolean(
        string="The cashier chooses the account",
        help="Before sending the amount to the terminal, the cashier picks the deposit account; this terminal's account comes selected.",
    )

    def _get_payment_terminal_selection(self):
        return super()._get_payment_terminal_selection() + [('xpago', "XPago")]

    @api.constrains('use_payment_terminal', 'xpago_provider_id', 'xpago_terminal_serial')
    def _check_xpago_terminal(self):
        for method in self.filtered(lambda m: m.use_payment_terminal == 'xpago'):
            if not method.xpago_provider_id or not method.xpago_terminal_serial:
                raise UserError(_("Choose the XPago account and write the serial number of the terminal."))

    def _xpago_check_access(self):
        self.ensure_one()
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("Only point of sale users can charge on XPago terminals."))
        if self.use_payment_terminal != 'xpago':
            raise UserError(_("This payment method does not use an XPago terminal."))
        provider = self.sudo().xpago_provider_id
        if provider.state == 'disabled':
            raise UserError(_("XPago is disabled. An administrator can enable it in the XPago payment provider."))
        return provider

    def _xpago_charge_account(self, provider, chosen_id=None, rule_account_id=None):
        """The cashier's choice when this terminal lets her choose, then the account of the payment rules of the
        sale, then the terminal's account."""
        Account = self.env['payment.xpago.bank.account'].sudo()
        chosen = Account.browse(int(chosen_id)).exists() if chosen_id and self.xpago_choose_account else Account
        rule_account = Account.browse(int(rule_account_id)).exists() if rule_account_id else Account
        # Only an account a payment rule names can come from the plan of the register.
        if rule_account and not self.env['payment.xpago.rule'].sudo().search_count(
                [('bank_account_id', '=', rule_account.id)], limit=1):
            rule_account = Account
        for account in (chosen, rule_account, self.sudo().xpago_bank_account_id):
            if provider._xpago_bank_account_id(account):
                return account
        return Account

    def _xpago_charge(self, charge_id):
        charge = self.env['pos.xpago.charge'].sudo().browse(int(charge_id)).exists()
        if not charge or charge.payment_method_id != self:
            raise UserError(_("This XPago charge does not exist."))
        return charge

    # Called by the point of sale

    def xpago_create_charge(self, data):
        """Send the amount to the terminal. Returns the charge as the point of sale sees it."""
        provider = self._xpago_check_access()
        session = self.env['pos.session'].browse(data.get('session_id')).exists()
        account = self._xpago_charge_account(provider, data.get('bank_account_id'), data.get('rule_account_id'))
        charge = self.env['pos.xpago.charge'].sudo()._xpago_create(
            self.sudo(), provider, data.get('amount') or 0.0, session, data.get('order_uuid') or '', account=account)
        return charge._xpago_public_view()

    def xpago_charge_status(self, charge_id):
        self._xpago_check_access()
        charge = self._xpago_charge(charge_id)
        charge._xpago_refresh()
        return charge._xpago_public_view()

    def xpago_cancel_charge(self, charge_id):
        self._xpago_check_access()
        charge = self._xpago_charge(charge_id)
        charge._xpago_cancel()
        return charge._xpago_public_view()

    def xpago_refund_charge(self, data):
        """A refund order paid back with this method: the terminal charge of the original sale for that amount goes
        back to the same card. XPago refunds a terminal charge in full and the same day only."""
        self._xpago_check_access()
        amount = -(data.get('amount') or 0.0)
        if amount <= 0:
            raise UserError(_("A refund is paid back with a negative amount."))
        orders = self.env['pos.order'].browse(data.get('refunded_order_ids') or []).exists()
        payments = orders.sudo().payment_ids.filtered(lambda p: p.payment_method_id == self and p.transaction_id)
        Charge = self.env['pos.xpago.charge'].sudo()
        charges = Charge.search([('payment_method_id', '=', self.id), ('state', 'in', ('confirmed', 'refunded')), '|',
                                 ('payment_id', 'in', payments.mapped('transaction_id')), ('pos_order_id', 'in', orders.ids)])
        # A charge refunded outside Odoo (terminal app, dashboard) is paid back here once: its refund order links it.
        linked = self.env['pos.payment'].sudo().search([
            ('payment_method_id', '=', self.id), ('amount', '<', 0),
            ('transaction_id', 'in', charges.filtered(lambda c: c.state == 'refunded').mapped('payment_id')),
        ]).mapped('transaction_id')
        charges = charges.filtered(lambda c: c.state == 'confirmed' or c.payment_id not in linked)
        currency = self.company_id.currency_id or self.env.company.currency_id
        charge = charges.filtered(lambda c: not currency.compare_amounts(c.amount, amount))[:1]
        if not charge:
            if charges:
                raise UserError(_(
                    "XPago gives back a card payment in full only. Refund %(amounts)s, or pay this refund another way.",
                    amounts=", ".join(currency.format(c.amount) for c in charges)))
            raise UserError(_("No card payment of this method was found in the original sale."))
        if charge.state == 'confirmed':
            try:
                charge._xpago_refund()
            except UserError as error:
                if getattr(error, 'xpago_code', None) != 'refund_fee_not_covered':
                    raise
                # The processor keeps its fee and today's card sales do not cover it; its terminal app refunds
                # anyway. The register waits for that refund (xpago_refund_status) and completes the line.
                return {'state': charge.state, 'wait_on_terminal': True, 'charge_id': charge.id, 'message': _(
                    "The processor does not accept this refund from Odoo: today's card sales do not cover its fee. "
                    "Refund it on the terminal (Transactions › the charge › Refund charge). The register is waiting "
                    "and completes it on its own; then press Validate."), 'stop_label': _("Stop waiting")}
        return {'state': charge.state, 'payment': charge._xpago_payment_values()}

    def xpago_refund_status(self, data):
        """The register waiting for a refund made on the terminal: ``refunded`` with the card once it is done."""
        self._xpago_check_access()
        charge = self.env['pos.xpago.charge'].sudo().search(
            [('id', '=', int(data.get('charge_id') or 0)), ('payment_method_id', '=', self.id)], limit=1)
        if not charge:
            raise UserError(_("No card payment of this method was found in the original sale."))
        if charge.state == 'confirmed':
            charge._xpago_read_refunded()
        if charge.state != 'refunded':
            return {'state': charge.state}
        linked = self.env['pos.payment'].sudo().search_count([
            ('payment_method_id', '=', self.id), ('amount', '<', 0), ('transaction_id', '=', charge.payment_id)])
        if linked:
            raise UserError(_("This charge was already refunded."))
        return {'state': 'refunded', 'payment': charge._xpago_payment_values()}

    def xpago_plan(self, data):
        """How the register charges this sale, by the XPago payment rules: one part, or one per account and months
        when the point of sale splits the charge. ``data``: ``session_id``, ``lines`` (``product_id``, ``qty``,
        ``amount`` with taxes), ``total`` (the sale) and ``amount`` (this payment).

        The terminal does not take the months: at the register they are only shown to the cashier."""
        self._xpago_check_access()
        session = self.env['pos.session'].browse(data.get('session_id')).exists()
        config = session.config_id
        Product = self.env['product.product'].with_context(active_test=False)
        lines = [{'product': Product.browse(int(line['product_id'])).exists(),
                  'unit_price': (line.get('amount') or 0.0) / line['qty'], 'amount': line.get('amount') or 0.0}
                 for line in data.get('lines') or [] if line.get('product_id') and line.get('qty')]
        total, amount = data.get('total') or 0.0, data.get('amount') or 0.0
        company = self.company_id or self.env.company
        # Splitting only makes sense when this payment is the whole sale.
        split = bool(config.xpago_split) and not company.currency_id.compare_amounts(total, amount)
        parts = self.env['payment.xpago.rule']._xpago_plan(company, 'pos', lines, total, config=config, split=split)
        if len(parts) == 1:
            parts[0]['amount'] = amount
        provider = self.sudo().xpago_provider_id
        return {
            'show_account': bool(config.xpago_show_account),
            'parts': [{'amount': part['amount'],
                       'account_id': part['account'].id if provider._xpago_bank_account_id(part['account']) else False,
                       'account_name': part['account'].name if provider._xpago_bank_account_id(part['account']) else '',
                       'terms': part['terms'] or False,
                       'rules': part['rules'].mapped('name')} for part in parts],
        }
