from unittest.mock import patch

import requests

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.xpago import const
from odoo.addons.xpago.tests.common import XpagoCommon

SEND = 'odoo.addons.xpago.models.payment_provider.PaymentProvider._send_api_request'


@tagged('post_install', '-at_install')
class TestPaymentXpago(XpagoCommon, PaymentHttpCommon):

    def test_checkout_is_created_and_customer_sent_to_it(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id)
        with patch(SEND, return_value=self.checkout) as send:
            values = self.safe(tx)._get_specific_rendering_values(None)
        method, endpoint = send.call_args.args
        payload = send.call_args.kwargs['json']
        self.assertEqual((method, endpoint), ('POST', '/v1/checkouts'))
        self.assertEqual(payload['reference'], tx.reference)
        self.assertTrue(payload['return_url'].endswith(const.PAYMENT_RETURN_ROUTE))
        self.assertEqual(send.call_args.kwargs['idempotency_key'], f'checkout-{tx.reference}')
        self.assertEqual(tx.provider_reference, self.checkout_id)
        self.assertEqual(values['url_params'], {'lang': 'es'})

    def test_refused_checkout_marks_the_transaction_in_error(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id)
        with patch(SEND, side_effect=ValidationError('nope')):
            self.assertEqual(self.safe(tx)._get_specific_rendering_values(None), {})
        self.assertEqual(tx.state, 'error')

    def test_months_without_interest_by_amount(self):
        self.provider.xpago_installment_rule_ids = [(0, 0, {'min_amount': 0, 'terms': ''}),
                                                    (0, 0, {'min_amount': 3000, 'terms': '3'}),
                                                    (0, 0, {'min_amount': 12000, 'terms': '3, 6, 12'})]
        self.assertEqual(self.provider._xpago_allowed_terms(800), [1])
        self.assertEqual(self.provider._xpago_allowed_terms(5000), [1, 3])
        self.assertEqual(self.provider._xpago_allowed_terms(15000), [1, 3, 6, 12])
        self.provider.xpago_single_payment = False
        self.assertEqual(self.provider._xpago_allowed_terms(15000), [3, 6, 12])

    def test_without_rules_every_plan_is_offered(self):
        self.assertIsNone(self.provider._xpago_allowed_terms(15000))

    def test_wrong_months_are_refused(self):
        with self.assertRaises(ValidationError):
            self.provider.xpago_installment_rule_ids = [(0, 0, {'min_amount': 0, 'terms': '3, 99'})]

    def test_confirmed_payment_is_done(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, provider_reference=self.checkout_id)
        self.safe(tx)._process(self.payment_data())
        self.assertEqual(tx.state, 'done')

    def test_cancelled_and_expired_checkouts_are_canceled(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, provider_reference=self.checkout_id)
        self.safe(tx)._process(self.payment_data('expired'))
        self.assertEqual(tx.state, 'cancel')

    def test_pending_checkout_stays_pending(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, provider_reference=self.checkout_id)
        self.safe(tx)._process(self.payment_data('pending'))
        self.assertEqual(tx.state, 'pending')

    @mute_logger('odoo.addons.xpago.controllers.main')
    def test_return_reads_back_the_payment(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, provider_reference=self.checkout_id)
        url = self._build_url(const.PAYMENT_RETURN_ROUTE)
        with patch(SEND, return_value=self.payment_data()) as send:
            self._make_http_get_request(url, params={'id': self.checkout_id, 'reference': tx.reference})
        self._run_processing()
        self.assertEqual(send.call_args.args, ('GET', f'/v1/checkouts/{self.checkout_id}'))
        self.assertEqual(tx.state, 'done')

    def test_cron_settles_a_payment_whose_customer_closed_the_page(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, provider_reference=self.checkout_id)
        with patch(SEND, return_value=self.payment_data()):
            self.env['payment.transaction']._xpago_cron_sync_pending()
        self._run_processing()
        self.assertEqual(tx.state, 'done')

    def test_paid_payment_notifies_the_chosen_users_once(self):
        boss = self.env['res.users'].create({'name': 'Dueña', 'login': 'duena-xp', 'group_ids': [(4, self.env.ref('base.group_user').id)]})
        self.provider.xpago_notify_user_ids = boss
        tx = self._create_transaction('redirect', currency_id=self.currency.id, provider_reference=self.checkout_id)
        self.safe(tx)._process(self.payment_data())
        self.safe(tx)._set_done()
        messages = self.env['mail.message'].sudo().search([('notified_partner_ids', 'in', boss.partner_id.ids)])
        self.assertEqual(len(messages), 1)
        self.assertIn('Payment received', messages.subject)

    def test_xpago_key_is_sent_to_the_xpago_api(self):
        self.assertEqual(self.provider._build_request_url('/v1/account'), const.API_URL + '/v1/account')
        self.env['ir.config_parameter'].sudo().set_str(const.API_URL_PARAM, 'http://127.0.0.1:8077/')
        self.assertEqual(self.provider._build_request_url('/v1/account'), 'http://127.0.0.1:8077/v1/account')
        headers = self.provider._build_request_headers('POST', '/x', None, idempotency_key='k-1')
        self.assertEqual(headers['Authorization'], 'Bearer xpk_test_key')
        self.assertEqual(headers['Idempotency-Key'], 'k-1')
        self.assertNotIn('Idempotency-Key', self.provider._build_request_headers('GET', '/x', None))

    def test_key_must_match_the_mode(self):
        self.provider.is_live = False
        with self.assertRaises(ValidationError):
            self.provider.write({'is_live': True})
        self.provider.write({'xpago_api_key': 'xpk_live_key', 'is_live': True})
        with self.assertRaises(ValidationError):
            self.provider.write({'xpago_api_key': 'xpk_test_key'})

    def test_a_key_that_is_not_an_xpago_key_asks_to_connect(self):
        self.assertFalse(self.provider.xpago_needs_connect)
        self.env.cr.execute("UPDATE payment_provider SET xpago_api_key = 'old-processor-key' WHERE id = %s", [self.provider.id])
        self.provider.invalidate_recordset()
        self.assertTrue(self.provider.xpago_needs_connect)
        self.assertIn(self.provider, self.env['payment.provider']._xpago_providers_to_connect(self.provider.company_id))
        self.assertTrue(self.provider.active, 'nothing is disabled')
        with patch(SEND) as send:
            self.provider._xpago_sync_bank_accounts()
        send.assert_not_called()
        action = self.provider.action_xpago_connect()
        self.assertEqual((action['type'], action['url']), ('ir.actions.act_url', const.CONNECT_URL))
        self.env['ir.config_parameter'].sudo().set_str(const.CONNECT_URL_PARAM, 'https://example.mx/conectar')
        self.assertEqual(self.provider.action_xpago_connect()['url'], 'https://example.mx/conectar')

    def test_error_message_of_the_api_is_shown(self):
        response = requests.Response()
        response.status_code = 403
        response._content = b'{"error": {"code": "merchant_suspended", "message": "This XPago account is suspended."}}'
        self.assertEqual(self.provider._parse_response_error(response), 'This XPago account is suspended.')
        response._content = (b'{"error": {"code": "invalid_request", "message": "The request is not valid.",'
                              b' "details": {"fields": [{"field": "currency", "message": "Input should be MXN"}]}}}')
        self.assertEqual(self.provider._parse_response_error(response),
                         'The request is not valid. currency: Input should be MXN')

    def test_enabling_without_api_key_is_refused(self):
        with self.assertRaises(ValidationError):
            self.provider.write({'xpago_api_key': False, 'is_live': True})


@tagged('post_install', '-at_install')
class TestDepositAccounts(XpagoCommon):

    ACCOUNTS = {'routing': 'manual', 'data': [{'id': 'acc-oper', 'name': 'Banorte Operación', 'is_default': True},
                                              {'id': 'acc-fiscal', 'name': 'BBVA Fiscal', 'is_default': False}]}

    def sync(self, answer=None):
        with patch(SEND, return_value=answer or self.ACCOUNTS) as send:
            self.provider._xpago_sync_bank_accounts()
        self.assertEqual(send.call_args.args, ('GET', '/v1/deposit-accounts'))
        return {a.xpago_id: a for a in self.provider.with_context(active_test=False).xpago_bank_account_ids}

    def test_accounts_are_read_updated_and_archived(self):
        accounts = self.sync()
        self.assertEqual(set(accounts), {'acc-oper', 'acc-fiscal'})
        self.assertTrue(accounts['acc-oper'].is_default)
        accounts = self.sync({'data': [{'id': 'acc-oper', 'name': 'Banorte', 'is_default': True}]})
        self.assertEqual(accounts['acc-oper'].name, 'Banorte')
        self.assertFalse(accounts['acc-fiscal'].active)

    def test_payment_goes_to_its_account(self):
        accounts = self.sync()
        self.provider.xpago_other_bank_account_id = accounts['acc-oper']
        tx = self._create_transaction('redirect', currency_id=self.currency.id)
        self.assertEqual(tx._xpago_prepare_checkout_payload()['deposit_account_id'], 'acc-oper')

    def test_archived_account_is_not_sent(self):
        accounts = self.sync()
        self.provider.xpago_other_bank_account_id = accounts['acc-fiscal']
        self.sync({'data': [{'id': 'acc-oper', 'name': 'Banorte', 'is_default': True}]})
        tx = self._create_transaction('redirect', currency_id=self.currency.id)
        self.assertNotIn('deposit_account_id', tx._xpago_prepare_checkout_payload())
