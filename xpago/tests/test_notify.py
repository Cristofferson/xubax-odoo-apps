import hashlib
import hmac
import json
import time
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.xpago import const
from odoo.addons.xpago.tests.common import XpagoCommon

SEND = 'odoo.addons.xpago.models.payment_provider.PaymentProvider._send_api_request'
SECRET = 'xpn_test_notify_secret_0123456789'


def sign(body, secret=SECRET, timestamp=None):
    timestamp = str(int(time.time()) if timestamp is None else timestamp)
    signature = 'v1=' + hmac.new(secret.encode(), f'{timestamp}.'.encode() + body, hashlib.sha256).hexdigest()
    return {const.NOTIFY_TIMESTAMP_HEADER: timestamp, const.NOTIFY_SIGNATURE_HEADER: signature,
            'Content-Type': 'application/json'}


@tagged('post_install', '-at_install')
class TestXpagoNotify(XpagoCommon, PaymentHttpCommon):

    def setUp(self):
        super().setUp()
        self.provider.sudo().write({'xpago_notify_secret': SECRET,
                                    'xpago_notify_url': self.provider._xpago_notify_endpoint()})

    def notice(self, obj, type_='one_time_payment.paid'):
        return json.dumps({'event_id': 'evt_1', 'type': type_, 'object': obj}).encode()

    def post(self, body, headers):
        return self.url_open(self._build_url(const.NOTIFY_ROUTE), data=body, headers=headers, method='POST')

    # === Signature === #

    @mute_logger('odoo.addons.xpago.controllers.main')
    def test_unsigned_or_badly_signed_notice_is_refused(self):
        body = self.notice({'kind': 'checkout', 'id': self.checkout_id})
        with patch(SEND) as send:
            self.assertEqual(self.post(body, {'Content-Type': 'application/json'}).status_code, 401)
            self.assertEqual(self.post(body, sign(body, secret='xpn_someone_else')).status_code, 401)
            self.assertEqual(self.post(body + b' ', {**sign(body)}).status_code, 401, 'the body was changed')
        send.assert_not_called()

    @mute_logger('odoo.addons.xpago.controllers.main')
    def test_old_notice_is_refused(self):
        body = self.notice({'kind': 'checkout', 'id': self.checkout_id})
        with patch(SEND) as send:
            self.assertEqual(self.post(body, sign(body, timestamp=int(time.time()) - 6 * 60)).status_code, 401)
        send.assert_not_called()

    def test_verify_picks_the_provider_of_the_secret(self):
        body = b'{}'
        headers = sign(body)
        found = self.env['payment.provider']._xpago_verify_notice(
            body, headers[const.NOTIFY_TIMESTAMP_HEADER], headers[const.NOTIFY_SIGNATURE_HEADER])
        self.assertEqual(found, self.provider)
        self.assertFalse(self.env['payment.provider']._xpago_verify_notice(body, 'not-a-time', 'v1=00'))

    # === Settling === #

    def test_notice_settles_the_pending_online_payment(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, provider_reference=self.checkout_id,
                                      state='pending')
        body = self.notice({'kind': 'checkout', 'id': self.checkout_id, 'payment_id': 'pay-1',
                            'reference': tx.reference})
        with patch(SEND, return_value=self.payment_data('paid')) as send:
            response = self.post(body, sign(body))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(send.call_args.args, ('GET', f'/v1/checkouts/{self.checkout_id}'), 'Odoo reads it again')
        self._run_processing()
        self.assertEqual(tx.state, 'done')

    def test_notice_body_decides_nothing(self):
        """A notice says paid; XPago, asked, says still pending: the payment stays pending."""
        tx = self._create_transaction('redirect', currency_id=self.currency.id, provider_reference=self.checkout_id,
                                      state='pending')
        body = self.notice({'kind': 'checkout', 'id': self.checkout_id, 'status': 'paid'})
        with patch(SEND, return_value=self.payment_data('pending')):
            self.assertEqual(self.post(body, sign(body)).status_code, 200)
        self._run_processing()
        self.assertEqual(tx.state, 'pending')

    @mute_logger('odoo.addons.xpago.models.payment_provider')
    def test_xpago_down_still_answers_200(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, provider_reference=self.checkout_id,
                                      state='pending')
        body = self.notice({'kind': 'checkout', 'id': self.checkout_id})
        with patch(SEND, side_effect=ValidationError('No connection with XPago.')):
            self.assertEqual(self.post(body, sign(body)).status_code, 200)
        self.assertEqual(tx.state, 'pending', 'the scheduled action reads it later')

    def test_unknown_or_finished_objects_are_ignored(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, provider_reference=self.checkout_id,
                                      state='done')
        with patch(SEND) as send:
            for obj in ({'kind': 'checkout', 'id': self.checkout_id}, {'kind': 'checkout', 'id': 'other'},
                        {'kind': 'deposit', 'id': 'po-1'}, {}):
                body = self.notice(obj)
                self.assertEqual(self.post(body, sign(body)).status_code, 200)
            self.assertEqual(self.post(b'not json', sign(b'not json')).status_code, 200)
        send.assert_not_called()
        self.assertEqual(tx.state, 'done')

    def test_saved_card_notice_reads_the_card_payment(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, state='pending', xpago_card_id='pm-1',
                                      provider_reference='pay-7')
        answers = {'/v1/saved-cards/pm-1': {'id': 'pm-1', 'status': 'active', 'card': {'last4': '4242'}},
                   '/v1/saved-cards/pm-1/payments/pay-7': {'id': 'pay-7', 'status': 'paid', 'amount': self.amount,
                                                           'currency': 'MXN'}}
        with patch(SEND, side_effect=lambda method, endpoint, **kw: answers[endpoint]):
            done = self.provider._xpago_handle_notice({'object': {'kind': 'saved_card', 'id': 'pm-1', 'payment_id': 'pay-7'}})
        self.assertEqual(done, [tx])
        self._run_processing()
        self.assertEqual(tx.state, 'done')

    # === Registration === #

    def test_button_registers_this_odoo(self):
        self.provider.sudo().write({'xpago_notify_secret': False, 'xpago_notify_url': False})
        self.assertTrue(self.provider._xpago_notify_needs_registration())
        url = self.provider._xpago_notify_endpoint()
        with patch(SEND, return_value={'url': url, 'secret': 'xpn_new', 'env': 'test'}) as send:
            action = self.provider.action_xpago_register_notify()
        self.assertEqual(send.call_args.args, ('PUT', '/v1/notify'))
        self.assertEqual(send.call_args.kwargs['json'], {'url': url})
        self.assertTrue(url.endswith(const.NOTIFY_ROUTE))
        self.assertEqual(action['params']['type'], 'success')
        self.assertEqual((self.provider.xpago_notify_url, self.provider.sudo().xpago_notify_secret), (url, 'xpn_new'))
        self.assertFalse(self.provider._xpago_notify_needs_registration())

    def test_button_shows_the_error(self):
        self.provider.sudo().write({'xpago_notify_secret': False, 'xpago_notify_url': False})
        with patch(SEND, side_effect=ValidationError('No connection with XPago.')):
            action = self.provider.action_xpago_register_notify()
        self.assertEqual(action['params']['type'], 'danger')
        self.assertFalse(self.provider.xpago_notify_url)

    def test_new_key_turns_notices_on_again(self):
        self.provider.write({'xpago_api_key': 'xpk_test_other'})
        self.assertFalse(self.provider.xpago_notify_url)
        self.assertFalse(self.provider.sudo().xpago_notify_secret)
        self.assertTrue(self.provider._xpago_notify_needs_registration())

    def test_moved_odoo_registers_again(self):
        self.provider.sudo().xpago_notify_url = 'https://old.example.com' + const.NOTIFY_ROUTE
        self.assertTrue(self.provider._xpago_notify_needs_registration())

    def test_scheduled_action_registers_when_missing(self):
        self.provider.sudo().write({'xpago_notify_secret': False, 'xpago_notify_url': False})

        def answer(method, endpoint, **kwargs):
            return {'data': []} if endpoint == '/v1/deposit-accounts' else {'url': kwargs['json']['url'], 'secret': 'xpn_cron'}

        with patch(SEND, side_effect=answer) as send:
            self.env['payment.provider']._xpago_cron_sync_bank_accounts()
        self.assertIn(('PUT', '/v1/notify'), [call.args for call in send.call_args_list])
        self.assertEqual(self.provider.sudo().xpago_notify_secret, 'xpn_cron')
        with patch(SEND, side_effect=answer) as send:
            self.env['payment.provider']._xpago_cron_sync_bank_accounts()
        self.assertNotIn(('PUT', '/v1/notify'), [call.args for call in send.call_args_list], 'registered once')

    def test_disabled_provider_is_not_registered(self):
        self.provider.sudo().write({'xpago_notify_secret': False, 'xpago_notify_url': False, 'active': False})
        self.assertFalse(self.provider._xpago_notify_needs_registration())
