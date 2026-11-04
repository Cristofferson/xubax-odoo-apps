from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    xpago_provider_id = fields.Many2one(
        'payment.provider', string="XPago account", domain="[('code', '=', 'xpago')]",
        default=lambda self: self.env['payment.provider'].search(
            [('code', '=', 'xpago'), ('company_id', 'in', self.env.company.parent_ids.ids)], order='company_id desc', limit=1),
        help="The XPago account this terminal charges with: its API key and whether it is in test mode.",
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

    @api.model
    def _load_pos_data_fields(self, config_id):
        return super()._load_pos_data_fields(config_id) + [
            'xpago_open_terminal_app', 'xpago_choose_account', 'xpago_bank_account_id']

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

    def _xpago_charge_account(self, provider, chosen_id=None):
        """The cashier's choice when this terminal lets her choose, else the terminal's account."""
        Account = self.env['payment.xpago.bank.account'].sudo()
        chosen = Account.browse(int(chosen_id)).exists() if chosen_id and self.xpago_choose_account else Account
        for account in (chosen, self.sudo().xpago_bank_account_id):
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
        account = self._xpago_charge_account(provider, data.get('bank_account_id'))
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
