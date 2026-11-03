from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment.logging import get_payment_logger
from odoo.addons.payment_xpago import const

_logger = get_payment_logger(__name__)


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
    xpago_notify_user_ids = fields.Many2many(
        'res.users', 'payment_xpago_notify_user_rel', 'provider_id', 'user_id', string="Notify payments to",
        domain=[('share', '=', False)],
        help="These users get an Odoo notification (inbox and pop-up) for each payment received with XPago.",
    )

    # === COMPUTE METHODS === #

    def _compute_feature_support_fields(self):
        """Override of `payment`: XPago refunds online payments from its own dashboard only."""
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'xpago').update({'support_refund': 'none'})

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

    # === REQUEST HELPERS === #

    def _build_request_url(self, endpoint, **kwargs):
        if self.code != 'xpago':
            return super()._build_request_url(endpoint, **kwargs)
        # A system parameter can point to another server (a local sandbox); never set in production.
        base_url = self.env['ir.config_parameter'].sudo().get_param('payment_xpago.api_url')
        return (base_url or const.API_URLS.get(self.state, const.API_URLS['test'])).rstrip('/') + endpoint

    def _build_request_headers(self, method, endpoint, payload, **kwargs):
        if self.code != 'xpago':
            return super()._build_request_headers(method, endpoint, payload, **kwargs)
        return {
            'x-api-key': self.sudo().xpago_api_key or '',
            'Accept': 'application/json',
            'User-Agent': 'odoo-xpago',
        }

    def _parse_response_error(self, response):
        if self.code != 'xpago':
            return super()._parse_response_error(response)
        body = response.json()
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

