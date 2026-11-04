import logging
import pprint
from datetime import timedelta
from urllib.parse import parse_qsl, urlparse

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment_xpago import const

_logger = logging.getLogger(__name__)


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
            created = self.provider_id._xpago_make_request(
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
            created = self.provider_id._xpago_make_request('POST', '/payment-method', json=payload)
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
        return self.provider_id._xpago_make_request(
            'GET', f'/developer/v1/one-time-payment/{self.provider_reference}',
        )

    def _xpago_fetch_card_data(self):
        """The saved card and the payment of this transaction on it."""
        card_id = self.xpago_card_id
        method = self.provider_id._xpago_make_request('GET', f'/payment-method/{card_id}')
        payment = None
        if self.provider_reference:
            payment = self.provider_id._xpago_make_request('GET', f'/payment-method/{card_id}/payment/{self.provider_reference}')
        elif self.operation != 'validation':
            listing = self.provider_id._xpago_make_request('GET', f'/payment-method/{card_id}/payment', params={'pageSize': 50})
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
                    tx._handle_notification_data('xpago', tx._xpago_fetch_payment_data())
            except ValidationError as error:
                _logger.warning("XPago: could not read back %s: %s", tx.reference, error)

    # === PROCESSING === #

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Override of `payment`: the transaction is the one read back, or the one of the reference XPago
        gives back (`externalId`)."""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'xpago' or len(tx) == 1:
            return tx
        reference = notification_data.get('externalId')
        if not reference:
            raise ValidationError("XPago: " + _("Received data with missing reference."))
        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'xpago')])
        if not tx:
            raise ValidationError("XPago: " + _("No transaction found matching reference %s.", reference))
        return tx

    def _process_notification_data(self, notification_data):
        """Override of `payment`: update the transaction from what XPago answered when asked."""
        super()._process_notification_data(notification_data)
        if self.provider_code != 'xpago':
            return
        _logger.info("XPago: processing %s with data:\n%s", self.reference, pprint.pformat(notification_data))
        if not self._xpago_amount_matches(notification_data):
            return
        if 'xpago_card' in notification_data or 'xpago_payment' in notification_data:
            self._xpago_apply_card_updates(notification_data)
        else:
            self._xpago_apply_checkout_updates(notification_data)
        if self.tokenize and self.state in ('authorized', 'done'):
            self._xpago_tokenize_from_notification_data(notification_data)

    def _xpago_amount_data(self, notification_data):
        """The amount and currency XPago reports, or None when nothing was paid yet."""
        if 'xpago_card' in notification_data or 'xpago_payment' in notification_data:
            payment = notification_data.get('xpago_payment')
            if not payment:
                return None  # The card is not saved yet: nothing was paid.
            held = payment.get('heldAmount')
            return float(held if held is not None else payment.get('amount') or 0), payment.get('currency') or 'MXN'
        if notification_data.get('amount') is None:
            return None
        return float(notification_data.get('amount') or 0), notification_data.get('currency')

    def _xpago_amount_matches(self, notification_data):
        """A payment of another amount or currency than the transaction's is never accepted."""
        if self.operation == 'validation':
            return True
        amount_data = self._xpago_amount_data(notification_data)
        if amount_data is None:
            return True
        amount, currency_code = amount_data
        if self.currency_id.compare_amounts(amount, self.amount) == 0 and (
                not currency_code or currency_code == self.currency_id.name):
            return True
        _logger.warning("XPago: %s expected %s %s and got %s %s", self.reference, self.amount,
                        self.currency_id.name, amount, currency_code)
        self._set_error(_("The amount or the currency of the payment does not match the transaction."))
        return False

    def _xpago_apply_checkout_updates(self, notification_data):
        if notification_data.get('id'):
            self.provider_reference = notification_data['id']
        status = notification_data.get('status')
        if status in const.STATUS_MAPPING['done']:
            terms = (notification_data.get('payment') or {}).get('terms') or notification_data.get('terms')
            if isinstance(terms, int) and terms > 1:
                self.xpago_terms = terms
            self._set_done()
        elif status in const.STATUS_MAPPING['canceled'] or notification_data.get('expired'):
            self._set_canceled()
        elif status in const.STATUS_MAPPING['pending']:
            self._set_pending()
        else:
            _logger.warning("XPago: unknown status %s for %s", status, self.reference)
            self._set_error(_("XPago answered an unknown status: %s", status))

    def _xpago_apply_card_updates(self, notification_data):
        method = notification_data.get('xpago_card') or {}
        payment = notification_data.get('xpago_payment')
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

    def _xpago_tokenize_from_notification_data(self, notification_data):
        """Save the card the customer saved in XPago as a payment token."""
        self.ensure_one()
        method = notification_data.get('xpago_card')
        if not method and self.xpago_card_id:
            method = self.provider_id._xpago_make_request('GET', f'/payment-method/{self.xpago_card_id}')
        if not method or method.get('status') != 'ACTIVE':
            return
        token = self.env['payment.token'].create({
            'provider_id': self.provider_id.id,
            'payment_method_id': self.payment_method_id.id,
            'partner_id': self.partner_id.id,
            'provider_ref': method['id'],
            'payment_details': (method.get('card') or {}).get('lastFourDigits') or '',
        })
        self.write({'token_id': token.id, 'tokenize': False})
        _logger.info("XPago: saved card %s as token %s for partner %s (%s)",
                     method['id'], token.id, self.partner_id.id, self.reference)

    # === TOKEN PAYMENTS, HOLDS AND REFUNDS === #

    def _send_payment_request(self):
        """Override of `payment`: charge (or hold) a saved card, for subscriptions and back-office payments."""
        super()._send_payment_request()
        if self.provider_code != 'xpago':
            return
        if not self.token_id:
            raise ValidationError("XPago: " + _("The transaction is not linked to a token."))
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
        self.xpago_card_id = card_id
        try:
            payment = self.provider_id._xpago_make_request('POST', f'/payment-method/{card_id}/payment', json=body)
        except ValidationError as error:
            self._set_error(str(error))
            return
        self._handle_notification_data('xpago', {'externalId': self.reference, 'xpago_payment': payment})

    def _xpago_held_payment_path(self):
        """The XPago path of the payment made on a saved card that this transaction (or its source) holds."""
        source = self.source_transaction_id or self
        if not source.xpago_card_id or not source.provider_reference:
            raise ValidationError(_("This payment was not made on a saved card: refund it from XPago's dashboard."))
        return f'/payment-method/{source.xpago_card_id}/payment/{source.provider_reference}'

    def _send_capture_request(self, amount_to_capture=None):
        """Override of `payment`: capture a hold in full or in part. XPago captures a hold only once: the rest of
        a partial capture is freed by the bank on its own."""
        if self.provider_code != 'xpago':
            return super()._send_capture_request(amount_to_capture=amount_to_capture)
        path = self._xpago_held_payment_path()
        capture_child_tx = super()._send_capture_request(amount_to_capture=amount_to_capture)
        partial = bool(capture_child_tx)
        payment = self.provider_id._xpago_make_request(
            'POST', path + '/capture', json={'amount': self.currency_id.round(amount_to_capture)} if partial else None,
        )
        if partial:
            capture_child_tx.provider_reference = payment.get('id') or self.provider_reference
            capture_child_tx._set_done()
            remainder = self._create_child_transaction(self.amount - capture_child_tx.amount)
            remainder._set_canceled(state_message=_("XPago captures a hold once; the bank frees the rest on its own."))
        else:
            self.provider_reference = payment.get('id') or self.provider_reference
            self._set_done()
        return capture_child_tx

    def _send_void_request(self, amount_to_void=None):
        """Override of `payment`: release a hold, which XPago does in full only."""
        if self.provider_code != 'xpago':
            return super()._send_void_request(amount_to_void=amount_to_void)
        if self.state != 'authorized':
            # The rest of a partially captured hold was already freed with its capture.
            return self.env['payment.transaction']
        if amount_to_void and self.currency_id.compare_amounts(amount_to_void, self.amount) < 0:
            raise ValidationError(_("XPago releases a hold in full only."))
        path = self._xpago_held_payment_path()
        void_child_tx = super()._send_void_request(amount_to_void=amount_to_void)
        self.provider_id._xpago_make_request('POST', path + '/release')
        self._set_canceled()
        return void_child_tx

    def _send_refund_request(self, amount_to_refund=None):
        """Override of `payment`: refund in full a payment made on a saved card. A one-time checkout is refunded
        from XPago's dashboard."""
        if self.provider_code != 'xpago':
            return super()._send_refund_request(amount_to_refund=amount_to_refund)
        path = self._xpago_held_payment_path()
        refund_tx = super()._send_refund_request(amount_to_refund=amount_to_refund)
        refunded = self.provider_id._xpago_make_request('POST', path + '/refund', json={'reason': refund_tx.reference})
        refund_tx.provider_reference = refunded.get('id') or self.provider_reference
        refund_tx._set_done()
        return refund_tx

    def _set_done(self, state_message=None, extra_allowed_states=()):
        txs = super()._set_done(state_message=state_message, extra_allowed_states=extra_allowed_states)
        for tx in txs.filtered(lambda t: t.provider_code == 'xpago' and t.operation != 'refund' and not t.xpago_notified):
            if tx.source_transaction_id.xpago_notified:
                continue  # The capture of a hold already notified when the hold was captured.
            (tx | tx.source_transaction_id).sudo().xpago_notified = True
            record = tx.invoice_ids[:1] if 'invoice_ids' in tx else None
            if not record and 'sale_order_ids' in tx:
                record = tx.sale_order_ids[:1]
            lines = [
                _("Online") if not tx.token_id else _("Saved card"),
                tx.partner_name,
                record.display_name if record else tx.reference,
                tx.xpago_terms > 1 and _("%s months without interest", tx.xpago_terms),
            ]
            tx.provider_id._xpago_notify(_("Payment received: %s", tx.currency_id.format(tx.amount)), lines, record or None)
        return txs
