from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.xpago.tests.common import XpagoCommon

SEND = 'odoo.addons.xpago.models.payment_provider.PaymentProvider._xpago_make_request'


@tagged('post_install', '-at_install')
class TestSavedCards(XpagoCommon):

    def setUp(self):
        super().setUp()
        self.partner.write({'email': 'cliente@ejemplo.mx', 'phone': '443 123 4567'})

    def card(self, status='active'):
        return {'id': 'pm-1', 'status': status, 'card': {'last4': '4242', 'brand': 'VISA'}}

    def card_payment(self, status='paid', amount=None, **extra):
        return {'id': 'cp-1', 'status': status, 'amount': amount or self.amount, 'currency': 'MXN', **extra}

    def test_saving_the_card_uses_the_card_checkout(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, tokenize=True)
        with patch(SEND, return_value={'id': 'pm-1', 'checkout_url': 'https://pay.example.com/card/pm-1'}) as send:
            values = tx._get_specific_rendering_values(None)
        self.assertEqual(send.call_args.args, ('POST', '/v1/saved-cards'))
        body = send.call_args.kwargs['json']
        self.assertEqual((body['collect'], body['amount']), ('charge', self.amount))
        self.assertEqual(body['customer']['phone'], '+524431234567')
        self.assertEqual((tx.xpago_card_id, values['api_url']), ('pm-1', 'https://pay.example.com/card/pm-1'))

    def test_card_checkout_without_phone_is_refused(self):
        self.partner.phone = False
        tx = self._create_transaction('redirect', currency_id=self.currency.id, tokenize=True, partner_phone=False)
        with patch(SEND) as send:
            self.assertEqual(tx._get_specific_rendering_values(None), {})
        send.assert_not_called()
        self.assertEqual(tx.state, 'error')

    def test_paid_card_checkout_creates_the_token(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, tokenize=True, xpago_card_id='pm-1')
        tx._handle_notification_data('xpago', {'reference': tx.reference, 'xpago_card': self.card(), 'xpago_payment': self.card_payment()})
        self.assertEqual(tx.state, 'done')
        self.assertEqual((tx.token_id.provider_ref, tx.token_id.payment_details), ('pm-1', '4242'))

    def test_saved_card_is_charged_for_a_subscription(self):
        token = self._create_token(provider_ref='pm-1')
        tx = self._create_transaction('token', currency_id=self.currency.id, token_id=token.id, operation='offline')
        with patch(SEND, return_value=self.card_payment()) as send:
            tx._send_payment_request()
        self.assertEqual(send.call_args.args, ('POST', '/v1/saved-cards/pm-1/payments'))
        self.assertEqual(send.call_args.kwargs['json']['reference'], tx.reference)
        self.assertFalse(send.call_args.kwargs['json']['hold'])
        self.assertEqual(tx.state, 'done')

    def test_declined_saved_card_is_an_error(self):
        token = self._create_token(provider_ref='pm-1')
        tx = self._create_transaction('token', currency_id=self.currency.id, token_id=token.id, operation='offline')
        with patch(SEND, side_effect=ValidationError('declined')):
            tx._send_payment_request()
        self.assertEqual(tx.state, 'error')

    def hold_mode(self):
        # Odoo holds only with the generic card method: the card brands do not support it.
        self.provider.payment_method_ids = self.provider.payment_method_ids.filtered(lambda m: m.code == 'card')
        self.provider.capture_manually = True

    def test_hold_then_partial_capture(self):
        self.hold_mode()
        token = self._create_token(provider_ref='pm-1')
        tx = self._create_transaction('token', currency_id=self.currency.id, token_id=token.id, operation='offline')
        with patch(SEND, return_value=self.card_payment('held', held_amount=self.amount)) as send:
            tx._send_payment_request()
        self.assertTrue(send.call_args.kwargs['json']['hold'])
        self.assertEqual(tx.state, 'authorized')
        with patch(SEND, return_value=self.card_payment('paid', amount=self.amount / 2)) as send:
            capture = tx._send_capture_request(amount_to_capture=self.amount / 2)
        self.assertEqual(send.call_args.args[1], '/v1/saved-cards/pm-1/payments/cp-1/capture')
        self.assertEqual(send.call_args.kwargs['json'], {'amount': 555.56})  # never 555.5600000000001
        self.assertEqual(capture.state, 'done')
        # XPago captures once: the rest of the hold is freed, and the hold itself ends confirmed.
        rest = tx.child_transaction_ids - capture
        self.assertEqual(rest.state, 'cancel')
        self.assertEqual(tx.state, 'done')
        with patch(SEND) as send:
            tx._send_void_request(amount_to_void=self.amount / 2)
        send.assert_not_called()

    def test_hold_then_full_capture(self):
        self.hold_mode()
        token = self._create_token(provider_ref='pm-1')
        tx = self._create_transaction('token', currency_id=self.currency.id, token_id=token.id, operation='offline')
        with patch(SEND, return_value=self.card_payment('held', held_amount=self.amount)):
            tx._send_payment_request()
        with patch(SEND, return_value=self.card_payment('paid')) as send:
            tx._send_capture_request()
        self.assertIsNone(send.call_args.kwargs['json'])
        self.assertEqual(tx.state, 'done')

    def test_hold_is_released(self):
        self.hold_mode()
        token = self._create_token(provider_ref='pm-1')
        tx = self._create_transaction('token', currency_id=self.currency.id, token_id=token.id, operation='offline')
        with patch(SEND, return_value=self.card_payment('held', held_amount=self.amount)):
            tx._send_payment_request()
        with patch(SEND, return_value={}) as send:
            tx._send_void_request()
        self.assertEqual(send.call_args.args[1], '/v1/saved-cards/pm-1/payments/cp-1/release')
        self.assertEqual(tx.state, 'cancel')

    def test_partial_release_is_refused(self):
        self.hold_mode()
        token = self._create_token(provider_ref='pm-1')
        tx = self._create_transaction('token', currency_id=self.currency.id, token_id=token.id, operation='offline')
        with patch(SEND, return_value=self.card_payment('held', held_amount=self.amount)):
            tx._send_payment_request()
        with patch(SEND) as send, self.assertRaises(ValidationError):
            tx._send_void_request(amount_to_void=self.amount / 2)
        send.assert_not_called()

    def test_saved_card_payment_is_refunded(self):
        token = self._create_token(provider_ref='pm-1')
        tx = self._create_transaction('token', currency_id=self.currency.id, token_id=token.id, operation='offline')
        with patch(SEND, return_value=self.card_payment()):
            tx._send_payment_request()
        with patch(SEND, return_value={'id': 'cp-1', 'status': 'refunded'}) as send:
            refund = tx._send_refund_request()
        self.assertEqual(send.call_args.args[1], '/v1/saved-cards/pm-1/payments/cp-1/refund')
        self.assertEqual((refund.state, refund.operation, refund.amount), ('done', 'refund', -self.amount))

    def test_checkout_is_refunded_the_same_day(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, provider_reference='chk-1', state='done')
        with patch(SEND, return_value={'id': 'chk-1', 'payment_id': 'pay-1', 'status': 'refunded'}) as send:
            refund = tx._send_refund_request()
        self.assertEqual(send.call_args.args, ('POST', '/v1/checkouts/chk-1/refund'))
        self.assertEqual((refund.state, refund.operation, refund.amount), ('done', 'refund', -self.amount))

    def test_checkout_refund_after_the_day_is_refused(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, provider_reference='chk-1', state='done')
        with patch(SEND, side_effect=ValidationError('The refund window expired.')), self.assertRaises(ValidationError):
            tx._send_refund_request()

    def test_archived_token_is_revoked(self):
        token = self._create_token(provider_ref='pm-1')
        with patch(SEND, return_value={}) as send:
            token.active = False
        self.assertEqual(send.call_args.args, ('DELETE', '/v1/saved-cards/pm-1'))
