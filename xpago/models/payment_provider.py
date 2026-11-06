import requests
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment.logging import get_payment_logger
from odoo.addons.xpago import const, failover

_logger = get_payment_logger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('xpago', "XPago")], ondelete={'xpago': 'set default'})
    xpago_api_key = fields.Char(
        string="XPago key", required_if_provider='xpago', copy=False, groups='base.group_system',
        help="The key XPago gave you when your account was opened: xpk_test_… charges nothing (test mode), "
             "xpk_live_… charges for real (enabled).",
    )
    xpago_installment_rule_ids = fields.One2many(
        'payment.xpago.installment.rule', 'provider_id', string="Months without interest", copy=True,
    )
    xpago_single_payment = fields.Boolean(
        string="Always offer a single payment", default=True,
        help="Offer paying in one go besides the months without interest of the amount.",
    )
    xpago_bank_account_ids = fields.One2many(
        'payment.xpago.bank.account', 'provider_id', string="Deposit accounts", context={'active_test': False},
    )
    xpago_invoice_bank_account_id = fields.Many2one(
        'payment.xpago.bank.account', string="Account for invoice payments", domain="[('provider_id', '=', id)]",
        help="Where XPago deposits the payments of invoices. Empty: your XPago account decides.",
    )
    xpago_other_bank_account_id = fields.Many2one(
        'payment.xpago.bank.account', string="Account for other online payments", domain="[('provider_id', '=', id)]",
        help="Where XPago deposits the online store, payment link and subscription payments. Empty: your XPago account decides.",
    )
    xpago_notify_user_ids = fields.Many2many(
        'res.users', 'payment_xpago_notify_user_rel', 'provider_id', 'user_id', string="Notify payments to",
        domain=[('share', '=', False)],
        help="These users get an Odoo notification (inbox and pop-up) for each payment received with XPago.",
    )

    xpago_needs_connect = fields.Boolean(
        compute='_compute_xpago_needs_connect',
        help="The key is not an XPago key (xpk_…): payments do not go through until the XPago account is connected.",
    )

    # === COMPUTE METHODS === #

    @api.depends('code', 'xpago_api_key')
    def _compute_xpago_needs_connect(self):
        for provider in self:
            key = provider.sudo().xpago_api_key or ''
            provider.xpago_needs_connect = provider.code == 'xpago' and not key.startswith(const.KEY_PREFIX)

    def _compute_feature_support_fields(self):
        """Override of `payment`: XPago saves cards, holds and captures once (in full or in part) and refunds a
        payment in full: a saved card's any day, a checkout's the same day."""
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'xpago').update({
            'support_tokenization': True,
            'support_manual_capture': 'partial',
            'support_refund': 'full_only',
        })

    # === CONSTRAINT METHODS === #

    @api.constrains('state', 'xpago_api_key')
    def _check_xpago_api_key_before_enabling(self):
        for provider in self.filtered(lambda p: p.code == 'xpago' and p.state != 'disabled'):
            key = provider.sudo().xpago_api_key
            if not key:
                raise ValidationError(_("Write the key XPago gave you before enabling it."))
            prefix = const.KEY_PREFIXES.get(provider.state)
            if prefix and not key.startswith(prefix):
                raise ValidationError(_(
                    "This XPago key does not match the state: test mode takes a key that starts with xpk_test_, "
                    "enabled takes one that starts with xpk_live_."))

    # === BUSINESS METHODS === #

    def _get_default_payment_method_codes(self):
        """Override of `payment` to return the default payment method codes."""
        self.ensure_one()
        if self.code != 'xpago':
            return super()._get_default_payment_method_codes()
        return const.DEFAULT_PAYMENT_METHOD_CODES

    def _xpago_allowed_terms(self, amount):
        """The months without interest the checkout offers for `amount`, with 1 for the single payment. None lets
        the checkout offer every plan of the XPago account."""
        self.ensure_one()
        rules = self.xpago_installment_rule_ids.sorted('min_amount')
        if not rules:
            return None
        rule = rules.filtered(lambda r: r.min_amount <= amount)[-1:]
        terms = rule._parse_terms() if rule else []
        return sorted({1, *terms} if self.xpago_single_payment or not terms else set(terms))

    @api.model
    def _xpago_connect_url(self):
        return self.env['ir.config_parameter'].sudo().get_param(const.CONNECT_URL_PARAM) or const.CONNECT_URL

    def action_xpago_connect(self):
        return {'type': 'ir.actions.act_url', 'url': self._xpago_connect_url(), 'target': 'new'}

    @api.model
    def _xpago_providers_to_connect(self, company=None):
        """The XPago providers of the company in use (enabled, in test, or holding a key) whose key is not an XPago
        key, for the warnings of the settings."""
        company = company or self.env.company
        providers = self.sudo().search([('code', '=', 'xpago'), ('company_id', 'in', company.parent_ids.ids)])
        return providers.filtered(lambda p: p.xpago_needs_connect and (p.state != 'disabled' or p.xpago_api_key))

    def _xpago_sync_bank_accounts(self):
        """Read the deposit accounts from XPago: new ones are added, renamed ones updated, removed ones archived."""
        Account = self.env['payment.xpago.bank.account'].sudo().with_context(active_test=False)
        for provider in self.filtered(lambda p: p.code == 'xpago' and p.state != 'disabled' and not p.xpago_needs_connect):
            answer = provider._send_api_request('GET', '/v1/deposit-accounts')
            existing = {account.xpago_id: account for account in Account.search([('provider_id', '=', provider.id)])}
            seen = set()
            for sequence, remote in enumerate(answer.get('data') or []):
                values = {'name': remote.get('name') or remote['id'], 'is_default': bool(remote.get('is_default')),
                          'sequence': sequence, 'active': True}
                seen.add(remote['id'])
                if remote['id'] in existing:
                    existing[remote['id']].write(values)
                else:
                    Account.create({**values, 'provider_id': provider.id, 'xpago_id': remote['id']})
            for xpago_id, account in existing.items():
                if xpago_id not in seen and account.active:
                    account.active = False

    def write(self, vals):
        res = super().write(vals)
        if {'xpago_api_key', 'state'} & set(vals) and any(p.code == 'xpago' for p in self):
            # Read the accounts a moment later, outside this request: a network call here could hold the record.
            self.env.ref('xpago.ir_cron_sync_bank_accounts')._trigger()
        return res

    @api.model
    def _xpago_cron_sync_bank_accounts(self):
        for provider in self.search([('code', '=', 'xpago')]):
            try:
                with self.env.cr.savepoint():
                    provider._xpago_sync_bank_accounts()
            except Exception as error:  # noqa: BLE001 - one account failing must not stop the others
                _logger.warning("XPago: could not read the deposit accounts of %s: %s", provider.name, error)

    def _xpago_bank_account_id(self, account):
        """The XPago id of a deposit account, when it is still active and belongs to this provider."""
        self.ensure_one()
        return account.xpago_id if account and account.active and account.provider_id == self else None

    # === REQUEST HELPERS === #

    def _xpago_api_urls(self):
        """The addresses of the XPago API, in the order they are tried."""
        params = self.env['ir.config_parameter'].sudo()
        single = (params.get_param(const.API_URL_PARAM) or '').strip()
        if single:
            return [single.rstrip('/')]
        listed = params.get_param(const.API_URLS_PARAM) or ''
        urls = [url.strip().rstrip('/') for url in listed.split(',') if url.strip()]
        return urls or list(const.API_URLS)

    def _build_request_url(self, endpoint, **kwargs):
        if self.code != 'xpago':
            return super()._build_request_url(endpoint, **kwargs)
        return self._xpago_api_urls()[0] + endpoint

    def _send_api_request(self, method, endpoint, *, params=None, data=None, json=None, reference=None, **kwargs):
        """As the payment module's, but over the list of XPago addresses (failover.py)."""
        if self.code != 'xpago':
            return super()._send_api_request(
                method, endpoint, params=params, data=data, json=json, reference=reference, **kwargs
            )
        self.ensure_one()
        payload = params or data or json
        headers = self._build_request_headers(method, endpoint, payload, **kwargs)
        urls = self._xpago_api_urls()
        self._log_request(method, urls[0] + endpoint, payload, reference=reference)
        try:
            response, _url = failover.send(
                method, urls, endpoint, memo_key=self.env.cr.dbname, headers=headers, params=params, json=json,
                data=data,
            )
        except failover.OutcomeUnknown:
            raise ValidationError(_(
                "XPago did not answer in time and this operation may have gone through. Check the terminal or the "
                "list of charges before trying again."
            )) from None
        except failover.Unreachable:
            raise ValidationError(_("No connection with XPago. Check the internet or try again in a moment.")) from None
        self._log_response(response, reference=reference)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            try:
                error_msg = self._parse_response_error(response)
            except ValueError:
                error_msg = response.text
            raise ValidationError(_("The payment provider rejected the request.\n%s", error_msg))
        return self._parse_response_content(response, **kwargs)

    def _build_request_headers(self, method, endpoint, payload, **kwargs):
        if self.code != 'xpago':
            return super()._build_request_headers(method, endpoint, payload, **kwargs)
        headers = {
            'Authorization': f'Bearer {self.sudo().xpago_api_key or ""}',
            'Accept': 'application/json',
            'User-Agent': 'odoo-xpago',
        }
        # A POST sent again with the same key (a lost connection, a double click) never charges twice.
        if kwargs.get('idempotency_key'):
            headers['Idempotency-Key'] = kwargs['idempotency_key']
        return headers

    def _parse_response_error(self, response):
        if self.code != 'xpago':
            return super()._parse_response_error(response)
        try:
            body = response.json()
        except ValueError:
            return response.text
        error = body.get('error') if isinstance(body, dict) and isinstance(body.get('error'), dict) else {}
        message = error.get('message') or error.get('code') or response.text
        fields = (error.get('details') or {}).get('fields') or []
        if fields:
            message += ' ' + '; '.join(f"{f.get('field')}: {f.get('message')}" for f in fields if isinstance(f, dict))
        return message

    # === NOTIFICATIONS === #

    def _xpago_notify(self, title, lines, record=None):
        """Tell the chosen users a payment came in: an inbox message (on the order or invoice when there is one, so
        it opens it) and a pop-up. A notification never stops a payment, so failures are only logged."""
        self.ensure_one()
        users = self.sudo().xpago_notify_user_ids.filtered('active')
        if not users:
            return
        lines = [line for line in lines if line]
        body = Markup('<p><b>%s</b></p><ul>%s</ul>') % (title, Markup('').join(Markup('<li>%s</li>') % line for line in lines))
        try:
            with self.env.cr.savepoint():
                thread = record.sudo() if record and 'message_notify' in record else self.env['mail.thread'].sudo()
                thread.message_notify(partner_ids=users.partner_id.ids, subject=title, body=body)
                for user in users:
                    user._bus_send('simple_notification', {
                        'type': 'success', 'title': title, 'message': ' · '.join(lines), 'sticky': False,
                    })
        except Exception:
            _logger.exception("XPago: could not notify the payment %s", title)

