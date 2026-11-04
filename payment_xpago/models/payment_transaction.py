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
    xpago_card_id = fields.Char(string="XPago saved card", readonly=True, copy=False, index=True,
                                help="The saved card (XPago payment method) this payment was made on.")
    xpago_notified = fields.Boolean(readonly=True, copy=False)

    # === CHECKOUT === #

    def _get_specific_rendering_values(self, processing_values):
        """Override of `payment`: create the XPago checkout and send the customer to it."""
        if self.provider_code != 'xpago':
            return super()._get_specific_rendering_values(processing_values)
        if self._xpago_uses_card_checkout():
            return self._xpago_card_checkout()
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

    def _xpago_deposit_account(self):
        """Invoice payments go to the invoice account, the rest to the other account."""
        provider = self.provider_id
        has_invoice = 'invoice_ids' in self and bool(self.invoice_ids)
        account = provider.xpago_invoice_bank_account_id if has_invoice else provider.xpago_other_bank_account_id
        return provider._xpago_bank_account_id(account)

    def _xpago_uses_card_checkout(self):
        """Saving the card, holding the amount or validating a card go through the card-saving checkout; a plain
        payment uses the one-time checkout."""
        return self.tokenize or self.provider_id.capture_manually or self.operation == 'validation'

    def _xpago_card_checkout(self):
        base_url = self.provider_id.get_base_url().rstrip('/')
        billing = self._xpago_billing()
        if not all(billing.values()):
            self._set_error(_("To save a card, the customer needs a name, an email and a phone number."))
            return {}
        payload = {
            'externalId': self.reference,
            'billingInformation': billing,
            'redirectUrl': base_url + const.CARD_RETURN_ROUTE,
            'ttlMinutes': const.CARD_CHECKOUT_TTL_MINUTES,
        }
        if self.operation != 'validation':
            payload['collectFunds'] = 'HOLD' if self.provider_id.capture_manually else 'CHARGE'
            payload['amount'] = self.currency_id.round(self.amount)
        try:
            created = self._send_api_request('POST', '/payment-method', json=payload)
        except ValidationError as error:
            self._set_error(str(error))
            return {}
        self.xpago_card_id = created['id']
        url = created['checkoutUrl']
        return {'api_url': url, 'url_params': dict(parse_qsl(urlparse(url).query))}

    def _xpago_billing(self):
        first, _space, last = (self.partner_name or '').strip().partition(' ')
        phone = ''.join(char for char in self.partner_phone or '' if char.isdigit())
        if phone and not (self.partner_phone or '').strip().startswith('+'):
            phone = '52' + phone[-10:] if len(phone) >= 10 else ''
        return {
            'email': (self.partner_email or '').strip(),
            'firstName': first.strip(),
            'lastName': last.strip() or first.strip(),
            'phoneNumber': '+' + phone if phone else '',
        }

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
        billing = self._xpago_billing()
        # XPago takes the customer whole or not at all; a partial one is filled in at checkout.
        if all(billing.values()):
            payload['billingInformation'] = billing
        account = self._xpago_deposit_account()
        if account:
            payload['bankAccountId'] = account
        terms = self.provider_id._xpago_allowed_terms(self.amount)
        if terms:
            payload['allowedTerms'] = terms
        return payload

    # === READING BACK === #

    def _xpago_fetch_payment_data(self):
        """XPago's view of the checkout. A return only says when to look; this is what decides."""
        self.ensure_one()
        if self.xpago_card_id:
            return self._xpago_fetch_card_data()
        return self._send_api_request(
            'GET', f'/developer/v1/one-time-payment/{self.provider_reference}',
        )

    def _xpago_fetch_card_data(self):
        """The saved card and the payment of this transaction on it."""
        card_id = self.xpago_card_id
        method = self._send_api_request('GET', f'/payment-method/{card_id}')
        payment = None
        if self.provider_reference:
            payment = self._send_api_request('GET', f'/payment-method/{card_id}/payment/{self.provider_reference}')
        elif self.operation != 'validation':
            listing = self._send_api_request('GET', f'/payment-method/{card_id}/payment', params={'pageSize': 50})
            items = [item for item in (listing or {}).get('items') or [] if isinstance(item, dict)]
            mine = [item for item in items if item.get('externalId') == self.reference]
            # The checkout's own payment carries no reference of its own.
            untagged = sorted((item for item in items if not item.get('externalId')), key=lambda item: item.get('createdAt') or '')
            payment = mine[0] if mine else (untagged[-1] if untagged and not self.token_id else None)
        return {'externalId': self.reference, 'xpago_card': method, 'xpago_payment': payment}

    @api.model
    def _xpago_cron_sync_pending(self):
        """Read back the checkouts still waiting, so a customer who paid and closed the page is not lost."""
        txs = self.search([
            ('provider_code', '=', 'xpago'),
            ('state', 'in', ('draft', 'pending')),
            '|', ('provider_reference', '!=', False), ('xpago_card_id', '!=', False),
            ('create_date', '>=', fields.Datetime.now() - timedelta(hours=const.SYNC_WINDOW_HOURS)),
        ])
        for tx in txs:
            try:
                with self.env.cr.savepoint():
                    tx._record(tx._xpago_fetch_payment_data())
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
        if 'xpago_operation' in payment_data:
            return None  # A capture, release or refund of a saved-card payment: XPago answers for that payment.
        if 'xpago_card' in payment_data or 'xpago_payment' in payment_data:
            payment = payment_data.get('xpago_payment')
            if not payment:
                return None  # The card is not saved yet: nothing was paid.
            held = payment.get('heldAmount')
            return {'amount': float(held if held is not None else payment.get('amount') or 0), 'currency_code': payment.get('currency') or 'MXN'}
        return {'amount': float(payment_data.get('amount') or 0), 'currency_code': payment_data.get('currency')}

    def _apply_updates(self, payment_data):
        if self.provider_code != 'xpago':
            return super()._apply_updates(payment_data)
        if 'xpago_operation' in payment_data:
            return self._xpago_apply_operation(payment_data['xpago_operation'], payment_data.get('xpago_answer') or {})
        if 'xpago_card' in payment_data or 'xpago_payment' in payment_data:
            return self._xpago_apply_card_updates(payment_data)
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

    def _xpago_apply_card_updates(self, payment_data):
        method = payment_data.get('xpago_card') or {}
        payment = payment_data.get('xpago_payment')
        if payment_data.get('xpago_card_id') and not self.xpago_card_id:
            self.xpago_card_id = payment_data['xpago_card_id']
        if payment and payment.get('id'):
            self.provider_reference = payment['id']
        if self.operation == 'validation' or not payment:
            status = method.get('status')
            if status in ('EXPIRED', 'REVOKED'):
                self._set_canceled(state_message=_("The card was not saved in time."))
            elif status == 'ACTIVE' and self.operation == 'validation':
                self._set_done()
            else:
                self._set_pending()
            return
        status = payment.get('status')
        if status in const.CARD_PAYMENT_STATUS['done']:
            self._set_done()
        elif status in const.CARD_PAYMENT_STATUS['authorized']:
            self._set_authorized()
        elif status in const.CARD_PAYMENT_STATUS['canceled']:
            self._set_canceled(state_message=_("The hold was released (%s).", status))
        elif status in const.CARD_PAYMENT_STATUS['error']:
            self._set_error(_("The bank declined the card."))
        elif status in const.CARD_PAYMENT_STATUS['pending']:
            self._set_pending()
        else:
            _logger.warning("XPago: unknown card payment status %s for %s", status, self.reference)
            self._set_error(_("XPago answered an unknown status: %s", status))

    def _extract_token_values(self, payment_data):
        if self.provider_code != 'xpago':
            return super()._extract_token_values(payment_data)
        method = payment_data.get('xpago_card')
        if not method and self.xpago_card_id:
            method = self._send_api_request('GET', f'/payment-method/{self.xpago_card_id}')
        if not method or method.get('status') != 'ACTIVE':
            return {}
        return {'provider_ref': method['id'], 'payment_details': (method.get('card') or {}).get('lastFourDigits') or ''}

    # === TOKEN PAYMENTS, HOLDS AND REFUNDS === #

    def _send_payment_request(self):
        """Override of `payment`: charge (or hold) a saved card, for subscriptions and back-office payments."""
        if self.provider_code != 'xpago':
            return super()._send_payment_request()
        card_id = self.token_id.provider_ref
        body = {
            'amount': self.currency_id.round(self.amount),
            'currency': 'MXN',
            'description': (self.reference or '')[:255],
            # Idempotency: the same reference sent again returns the first charge instead of a second one.
            'externalId': self.reference,
        }
        if self.provider_id.capture_manually:
            body['holdFunds'] = True
        # A refused charge raises: `_charge_with_token` puts the transaction in error.
        payment = self._send_api_request('POST', f'/payment-method/{card_id}/payment', json=body)
        self._record({'externalId': self.reference, 'xpago_card_id': card_id, 'xpago_payment': payment})

    def _xpago_held_payment_path(self):
        source = self.source_transaction_id
        if not source.xpago_card_id or not source.provider_reference:
            raise ValidationError(_("This payment was not made on a saved card: refund it from XPago's dashboard."))
        return f'/payment-method/{source.xpago_card_id}/payment/{source.provider_reference}'

    def _send_capture_request(self):
        if self.provider_code != 'xpago':
            return super()._send_capture_request()
        partial = self._xpago_is_partial()
        payment = self._send_api_request(
            'POST', self._xpago_held_payment_path() + '/capture',
            json={'amount': self.currency_id.round(self.amount)} if partial else None,
        )
        self._record({'externalId': self.reference, 'xpago_operation': 'capture', 'xpago_answer': payment})

    def _xpago_is_partial(self):
        return self.currency_id.compare_amounts(self.amount, self.source_transaction_id.amount) < 0

    def _send_void_request(self):
        if self.provider_code != 'xpago':
            return super()._send_void_request()
        if self.currency_id.compare_amounts(self.amount, self.source_transaction_id.amount) < 0:
            raise ValidationError(_("XPago releases a hold in full only."))
        released = self._send_api_request('POST', self._xpago_held_payment_path() + '/release')
        self._record({'externalId': self.reference, 'xpago_operation': 'void', 'xpago_answer': released})

    def _send_refund_request(self):
        if self.provider_code != 'xpago':
            return super()._send_refund_request()
        refunded = self._send_api_request('POST', self._xpago_held_payment_path() + '/refund', json={'reason': self.reference})
        self._record({'externalId': self.reference, 'xpago_operation': 'refund', 'xpago_answer': refunded})

    def _xpago_apply_operation(self, operation, answer):
        """What XPago answered to a capture, release or refund sent from Odoo: the request went through."""
        source = self.source_transaction_id
        if operation == 'void':
            self._set_canceled()
            return
        self.provider_reference = (answer or {}).get('id') or source.provider_reference
        self._set_done()
        if operation == 'capture' and self._xpago_is_partial():
            # XPago captures a hold only once: the rest of the hold is freed by the bank on its own.
            remainder = source._create_child_transaction(source.amount - self.amount)
            remainder._set_canceled(state_message=_("XPago captures a hold once; the bank frees the rest on its own."))

    def _set_done(self, **kwargs):
        txs = super()._set_done(**kwargs)
        for tx in txs.filtered(lambda t: t.provider_code == 'xpago' and t.operation != 'refund' and not t.xpago_notified):
            if tx.source_transaction_id.xpago_notified:
                continue  # The capture of a hold already notified when the hold was captured.
            (tx | tx.source_transaction_id).sudo().xpago_notified = True
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
