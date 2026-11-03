from urllib.parse import parse_qsl, urlparse

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment.logging import get_payment_logger
from odoo.addons.payment_xpago import const

_logger = get_payment_logger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    xpago_terms = fields.Integer(string="Months without interest", readonly=True, copy=False)
    xpago_notified = fields.Boolean(readonly=True, copy=False)

    # === CHECKOUT === #

    def _get_specific_rendering_values(self, processing_values):
        """Override of `payment`: create the XPago checkout and send the customer to it."""
        if self.provider_code != 'xpago':
            return super()._get_specific_rendering_values(processing_values)
        try:
            created = self._send_api_request(
                'POST', '/one-time-payment', json=self._xpago_prepare_checkout_payload(),
            )
        except ValidationError as error:
            self._set_error(str(error))
            return {}
        url = created.get('redirectUrl') or created.get('url')
        self.provider_reference = created.get('id') or urlparse(url).path.rstrip('/').rsplit('/', 1)[-1]
        # The form is sent with GET, which drops the query string of its action: keep it as inputs.
        return {'api_url': url, 'url_params': dict(parse_qsl(urlparse(url).query))}

    def _xpago_prepare_checkout_payload(self):
        base_url = self.provider_id.get_base_url().rstrip('/')
        payload = {
            'amount': self.currency_id.round(self.amount),
            'currency': self.currency_id.name,
            'externalId': self.reference,
            'description': f'{self.company_id.name} – {self.reference}'[:255],
            'homepageUrl': base_url,
            'redirectUrl': base_url + const.PAYMENT_RETURN_ROUTE,
        }
        first, _space, last = (self.partner_name or '').strip().partition(' ')
        billing = {
            'email': (self.partner_email or '').strip(),
            'firstName': first,
            'lastName': last.strip() or first,
            'phoneNumber': (self.partner_phone or '').strip(),
        }
        # XPago takes the customer whole or not at all; a partial one is filled in at checkout.
        if all(billing.values()):
            payload['billingInformation'] = billing
        terms = self.provider_id._xpago_allowed_terms(self.amount)
        if terms:
            payload['allowedTerms'] = terms
        return payload

    # === READING BACK === #

    def _xpago_fetch_payment_data(self):
        """XPago's view of the checkout. A return only says when to look; this is what decides."""
        self.ensure_one()
        return self._send_api_request(
            'GET', f'/developer/v1/one-time-payment/{self.provider_reference}',
        )

    @api.model
    def _xpago_cron_sync_pending(self):
        """Read back the checkouts still waiting, so a customer who paid and closed the page is not lost."""
        txs = self.search([
            ('provider_code', '=', 'xpago'),
            ('state', 'in', ('draft', 'pending')),
            ('provider_reference', '!=', False),
            ('create_date', '>=', fields.Datetime.now() - timedelta(hours=const.SYNC_WINDOW_HOURS)),
        ])
        for tx in txs:
            try:
                with self.env.cr.savepoint():
                    tx._process('xpago', tx._xpago_fetch_payment_data())
            except ValidationError as error:
                _logger.warning("XPago: could not read back %s: %s", tx.reference, error)

    # === PROCESSING === #

    @api.model
    def _extract_reference(self, provider_code, payment_data):
        if provider_code != 'xpago':
            return super()._extract_reference(provider_code, payment_data)
        return payment_data.get('externalId')

    def _extract_amount_data(self, payment_data):
        if self.provider_code != 'xpago':
            return super()._extract_amount_data(payment_data)
        return {'amount': float(payment_data.get('amount') or 0), 'currency_code': payment_data.get('currency')}

    def _apply_updates(self, payment_data):
        if self.provider_code != 'xpago':
            return super()._apply_updates(payment_data)
        if payment_data.get('id'):
            self.provider_reference = payment_data['id']
        status = payment_data.get('status')
        if status in const.STATUS_MAPPING['done']:
            terms = (payment_data.get('payment') or {}).get('terms') or payment_data.get('terms')
            if isinstance(terms, int) and terms > 1:
                self.xpago_terms = terms
            self._set_done()
        elif status in const.STATUS_MAPPING['canceled'] or payment_data.get('expired'):
            self._set_canceled()
        elif status in const.STATUS_MAPPING['pending']:
            self._set_pending()
        else:
            _logger.warning("XPago: unknown status %s for %s", status, self.reference)
            self._set_error(_("XPago answered an unknown status: %s", status))

    def _set_done(self, **kwargs):
        txs = super()._set_done(**kwargs)
        for tx in txs.filtered(lambda t: t.provider_code == 'xpago' and t.operation != 'refund' and not t.xpago_notified):
            tx.sudo().xpago_notified = True
            record = tx.invoice_ids[:1] if 'invoice_ids' in tx else self.env['account.move']
            record = record or (tx.sale_order_ids[:1] if 'sale_order_ids' in tx else record)
            lines = [
                _("Online") if not tx.token_id else _("Saved card"),
                tx.partner_name,
                record.display_name if record else tx.reference,
                tx.xpago_terms > 1 and _("%s months without interest", tx.xpago_terms),
            ]
            tx.provider_id._xpago_notify(_("Payment received: %s", tx.currency_id.format(tx.amount)), lines, record or None)
        return txs
