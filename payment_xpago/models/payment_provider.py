import logging
import pprint

import requests
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment_xpago import const

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('xpago', "XPago")], ondelete={'xpago': 'set default'})
    xpago_api_key = fields.Char(
        string="XPago API Key", required_if_provider='xpago', copy=False, groups='base.group_system',
        help="The API key XPago gave you when your account was opened.",
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

    # === COMPUTE METHODS === #

    def _compute_feature_support_fields(self):
        """Override of `payment`: XPago saves cards, holds and captures once (in full or in part) and refunds the
        payments made on a saved card in full. A one-time checkout is refunded from XPago's dashboard."""
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
            if not provider.sudo().xpago_api_key:
                raise ValidationError(_("Write the API key XPago gave you before enabling it."))

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

    def _xpago_sync_bank_accounts(self):
        """Read the deposit accounts from XPago: new ones are added, renamed ones updated, removed ones archived."""
        Account = self.env['payment.xpago.bank.account'].sudo().with_context(active_test=False)
        for provider in self.filtered(lambda p: p.code == 'xpago' and p.state != 'disabled' and p.sudo().xpago_api_key):
            answer = provider._xpago_make_request('GET', '/developer/v1/bank-account')
            existing = {account.xpago_id: account for account in Account.search([('provider_id', '=', provider.id)])}
            seen = set()
            for sequence, remote in enumerate(answer.get('data') or []):
                values = {'name': remote.get('name') or remote['id'], 'is_default': bool(remote.get('isDefault')),
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
            self.env.ref('payment_xpago.ir_cron_sync_bank_accounts')._trigger()
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

    def _xpago_api_url(self, endpoint):
        """The URL of an endpoint of XPago's API, in the environment the provider's state chooses."""
        self.ensure_one()
        # A system parameter can point to another server (a local sandbox); never set in production.
        base_url = self.env['ir.config_parameter'].sudo().get_param('payment_xpago.api_url')
        return (base_url or const.API_URLS.get(self.state, const.API_URLS['test'])).rstrip('/') + endpoint

    def _xpago_request_headers(self):
        self.ensure_one()
        return {
            'x-api-key': self.sudo().xpago_api_key or '',
            'Accept': 'application/json',
            'User-Agent': 'odoo-xpago',
        }

    def _xpago_make_request(self, method, endpoint, json=None, params=None):
        """Call XPago's API and return the JSON answer.

        :raise ValidationError: When XPago cannot be reached or refuses the request."""
        self.ensure_one()
        url = self._xpago_api_url(endpoint)
        try:
            response = requests.request(
                method, url, json=json, params=params, headers=self._xpago_request_headers(), timeout=30,
            )
        except requests.exceptions.RequestException as error:
            _logger.warning("XPago: unable to reach %s: %s", url, error)
            raise ValidationError("XPago: " + _("Could not establish the connection to the API.")) from error
        if not response.ok:
            _logger.warning("XPago: %s %s answered %s:\n%s", method, url, response.status_code,
                            pprint.pformat(response.text[:2000]))
            raise ValidationError("XPago: " + _(
                "The communication with the API failed. Details: %s", self._xpago_parse_response_error(response),
            ))
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as error:
            raise ValidationError("XPago: " + _("The API answered something that is not JSON.")) from error

    def _xpago_parse_response_error(self, response):
        try:
            body = response.json()
        except ValueError:
            return response.text or response.reason
        if not isinstance(body, dict):
            return response.text
        error = body.get('error') if isinstance(body.get('error'), dict) else body
        return error.get('message') or error.get('code') or response.text

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

