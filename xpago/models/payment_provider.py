import threading
import time

import requests
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.modules import module as odoo_module
from odoo.tools import SQL

from odoo.addons.payment.logging import get_payment_logger
from odoo.addons.xpago import const, failover

_logger = get_payment_logger(__name__)

# When each provider's connection status was last written by this worker, and whether that call worked.
_status_written = {}
_status_lock = threading.Lock()


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

    xpago_neutralized = fields.Boolean(
        string="Neutralized copy", readonly=True, copy=False,
        help="This database is a neutralized copy: XPago was switched off and its key removed, so the copy never "
             "charges with the real account. Write a test key to try XPago here.",
    )
    xpago_connection_state = fields.Selection(
        [('unknown', "Not checked yet"), ('ok', "Connected"), ('error', "Error")], string="Connection",
        compute='_compute_xpago_connection',
    )
    xpago_environment = fields.Selection(
        [('test', "Test (charges nothing)"), ('live', "Real")], string="Environment",
        compute='_compute_xpago_connection', help="Read from the XPago key: xpk_test_ or xpk_live_.",
    )
    xpago_account_name = fields.Char(string="XPago account", compute='_compute_xpago_connection')
    xpago_last_ok_at = fields.Datetime(string="Last call that worked", compute='_compute_xpago_connection')
    xpago_last_error_at = fields.Datetime(string="Last error at", compute='_compute_xpago_connection')
    xpago_last_error = fields.Char(string="Last error", compute='_compute_xpago_connection')

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

    @api.depends('xpago_api_key')
    def _compute_xpago_connection(self):
        statuses = {
            status.provider_id.id: status
            for status in self.env['payment.xpago.connection'].sudo().search([('provider_id', 'in', self.ids)])
        }
        for provider in self:
            status = statuses.get(provider.id)
            key = provider.sudo().xpago_api_key or ''
            provider.xpago_environment = (
                'test' if key.startswith('xpk_test_') else 'live' if key.startswith('xpk_live_') else False
            )
            provider.xpago_account_name = status.account_name if status else False
            provider.xpago_last_ok_at = status.last_ok_at if status else False
            provider.xpago_last_error_at = status.last_error_at if status else False
            provider.xpago_last_error = status.last_error if status else False
            # A call that works clears the error: the error shows only while it is the latest news.
            if not status or not (status.last_ok_at or status.last_error_at):
                provider.xpago_connection_state = 'unknown'
            else:
                provider.xpago_connection_state = 'error' if status.last_error else 'ok'

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

    @api.constrains('is_live', 'active', 'xpago_api_key')
    def _check_xpago_api_key_before_enabling(self):
        for provider in self.filtered(lambda p: p.code == 'xpago' and p.active):
            key = provider.sudo().xpago_api_key
            if not key:
                if provider.is_live:
                    raise ValidationError(_("Write the key XPago gave you before switching it to live."))
                continue
            prefix = const.KEY_PREFIXES[bool(provider.is_live)]
            if not key.startswith(prefix):
                raise ValidationError(_(
                    "This XPago key does not match the mode: out of live mode it takes a key that starts with "
                    "xpk_test_, in live mode one that starts with xpk_live_."))

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
        return self.env['ir.config_parameter'].sudo().get_str(const.CONNECT_URL_PARAM) or const.CONNECT_URL

    def action_xpago_connect(self):
        return {'type': 'ir.actions.act_url', 'url': self._xpago_connect_url(), 'target': 'new'}

    @api.model
    def _xpago_providers_to_connect(self, company=None):
        """The XPago providers of the company in use (enabled, in test, or holding a key) whose key is not an XPago
        key, for the warnings of the settings."""
        company = company or self.env.company
        providers = self.sudo().with_context(active_test=False).search(
            [('code', '=', 'xpago'), ('company_id', 'in', company.parent_ids.ids)])
        return providers.filtered(lambda p: p.xpago_needs_connect and (p.active or p.xpago_api_key))

    def _xpago_sync_bank_accounts(self):
        """Read the deposit accounts from XPago: new ones are added, renamed ones updated, removed ones archived."""
        Account = self.env['payment.xpago.bank.account'].sudo().with_context(active_test=False)
        for provider in self.filtered(lambda p: p.code == 'xpago' and p.active and not p.xpago_needs_connect):
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
        if vals.get('xpago_api_key'):
            vals = {**vals, 'xpago_neutralized': False}
        res = super().write(vals)
        if {'xpago_api_key', 'is_live', 'active'} & set(vals) and any(p.code == 'xpago' for p in self):
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

    # === CONNECTION STATUS === #

    def action_xpago_test_connection(self):
        """Ask XPago for the account of this key: proves the key, the environment and the way to XPago."""
        self.ensure_one()
        try:
            account = self._send_api_request('GET', '/v1/account')
        except ValidationError as error:
            self._xpago_save_status(ok=False, error=str(error))
            return self._xpago_notification(_("XPago did not answer"), str(error), 'danger')
        name = account.get('name') or account.get('legal_name') or ''
        self._xpago_save_status(ok=True, account_name=name)
        return self._xpago_notification(_("Connected to XPago"), name or _("The key works."), 'success')

    def _xpago_notification(self, title, message, kind):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': kind, 'sticky': kind == 'danger',
                       'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}},
        }

    def _xpago_save_status(self, ok, error=None, account_name=None):
        """The «Test connection» button: written at once, whatever the request does after."""
        self._xpago_store_status(ok, error=error, account_name=account_name, throttle=False)

    def _xpago_note_call(self, ok, error=None):
        """Remember how a call to XPago went, for the connection panel: a call that worked at most once a minute per
        worker, a failed one always. Never stops a payment."""
        self._xpago_store_status(ok, error=error, throttle=True)

    def _xpago_store_status(self, ok, error=None, account_name=None, throttle=True):
        """Write the connection status in its own short transaction, apart from the request's: it survives when the
        request fails, and it never holds or collides with anything a cashier needs. Tests use their own cursor."""
        self.ensure_one()
        if not self.id:
            return
        error = None if ok else ((error or '')[:500] or 'Error')
        if odoo_module.current_test:
            Status = self.env['payment.xpago.connection'].sudo()
            status = Status.search([('provider_id', '=', self.id)], limit=1) or Status.create({'provider_id': self.id})
            values = {'last_ok_at': fields.Datetime.now(), 'last_error': False} if ok else {
                'last_error_at': fields.Datetime.now(), 'last_error': error}
            if account_name is not None:
                values['account_name'] = account_name
            status.write(values)
            return
        key = (self.env.cr.dbname, self.id)
        now = time.monotonic()
        with _status_lock:
            last = _status_written.get(key)
            if throttle and ok and last and last[1] and now - last[0] < const.STATUS_WRITE_SECONDS:
                return
            _status_written[key] = (now, ok)
        column = SQL.identifier('last_ok_at' if ok else 'last_error_at')
        try:
            with self.env.registry.cursor() as cr:
                cr.execute(SQL(
                    """INSERT INTO payment_xpago_connection
                              (provider_id, %(column)s, last_error, account_name, create_date, write_date)
                       VALUES (%(provider)s, now() at time zone 'utc', %(error)s, %(account)s,
                               now() at time zone 'utc', now() at time zone 'utc')
                  ON CONFLICT (provider_id) DO UPDATE
                          SET %(column)s = EXCLUDED.%(column)s,
                              last_error = EXCLUDED.last_error,
                              account_name = COALESCE(EXCLUDED.account_name, payment_xpago_connection.account_name),
                              write_date = EXCLUDED.write_date""",
                    column=column, provider=self.id, error=error, account=account_name,
                ))
        except Exception as write_error:  # noqa: BLE001 - the panel never stops a payment
            _logger.info("XPago: could not write the connection status of %s: %s", self.id, write_error)

    # === REQUEST HELPERS === #

    def _xpago_api_urls(self):
        """The addresses of the XPago API, in the order they are tried."""
        params = self.env['ir.config_parameter'].sudo()
        single = (params.get_str(const.API_URL_PARAM) or '').strip()
        if single:
            return [single.rstrip('/')]
        listed = params.get_str(const.API_URLS_PARAM) or ''
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
            self._xpago_note_call(False, _("XPago did not answer in time."))
            raise ValidationError(_(
                "XPago did not answer in time and this operation may have gone through. Check the terminal or the "
                "list of charges before trying again."
            )) from None
        except failover.Unreachable:
            self._xpago_note_call(False, _("No connection with XPago."))
            raise ValidationError(_("No connection with XPago. Check the internet or try again in a moment.")) from None
        self._log_response(response, reference=reference)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            try:
                error_msg = self._parse_response_error(response)
            except ValueError:
                error_msg = response.text
            # A refused key or XPago failing is a connection problem; a refused request (a bad amount) is not.
            broken = response.status_code in (401, 403) or response.status_code >= 500
            self._xpago_note_call(not broken, error_msg if broken else None)
            known = self._xpago_known_refusal(response)
            if known:
                error = ValidationError(known)
                error.xpago_code = self._xpago_error_code(response)
                raise error
            raise ValidationError(self.env._("The payment provider rejected the request.\n%s", error_msg))
        self._xpago_note_call(True)
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

    def _xpago_error_code(self, response):
        try:
            error = (response.json() or {}).get('error') or {}
        except (ValueError, AttributeError):
            return None
        return error.get('code') if isinstance(error, dict) else None

    def _xpago_known_refusal(self, response):
        """The words for a refusal the cashier can act on, or None. Refunds: the processor keeps its fee and takes it
        from what the business has pending to settle; its terminal follows the same rule."""
        try:
            error = (response.json() or {}).get('error') or {}
        except (ValueError, AttributeError):
            return None
        if not isinstance(error, dict):
            return None
        code, details = error.get('code'), error.get('details') or {}
        currency = self.company_id.currency_id or self.env.company.currency_id
        if code == 'refund_fee_not_covered':
            required, missing = details.get('required'), details.get('missing')
            if isinstance(required, (int, float)) and isinstance(missing, (int, float)):
                return _(
                    "The processor does not accept this refund: it keeps its fee of %(required)s and the card sales "
                    "pending to settle do not cover it (%(missing)s missing). Nothing was charged back. It will go "
                    "through once there are more card sales today, or ask the processor for a refund allowance.",
                    required=currency.format(required), missing=currency.format(missing))
            return _(
                "The processor does not accept this refund: the card sales pending to settle do not cover its fee. "
                "Nothing was charged back. It will go through once there are more card sales today, or ask the "
                "processor for a refund allowance.")
        if code == 'refund_window_expired':
            return _("This charge can no longer be refunded: card refunds are accepted the same day only, before "
                     "10:30 PM (10:00 PM with American Express).")
        if code == 'already_refunded':
            return _("This charge was already refunded.")
        if code == 'refund_declined':
            return _("The customer's bank did not accept the refund. Nothing was charged back.")
        return None

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

