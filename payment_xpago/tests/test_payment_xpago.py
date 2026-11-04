from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.payment_xpago import const
from odoo.addons.payment_xpago.tests.common import XpagoCommon

SEND = 'odoo.addons.payment.models.payment_provider.PaymentProvider._send_api_request'


@tagged('post_install', '-at_install')
class TestPaymentXpago(XpagoCommon, PaymentHttpCommon):

    def test_checkout_is_created_and_customer_sent_to_it(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id)
        with patch(SEND, return_value=self.checkout) as send:
            values = self.safe(tx)._get_specific_rendering_values(None)
        method, endpoint = send.call_args.args
        payload = send.call_args.kwargs['json']
        self.assertEqual((method, endpoint), ('POST', '/one-time-payment'))
        self.assertEqual(payload['externalId'], tx.reference)
        self.assertTrue(payload['redirectUrl'].endswith(const.PAYMENT_RETURN_ROUTE))
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
        self.safe(tx)._process(self.payment_data('PENDING', expired=True))
        self.assertEqual(tx.state, 'cancel')

    def test_pending_checkout_stays_pending(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, provider_reference=self.checkout_id)
        self.safe(tx)._process(self.payment_data('PENDING'))
        self.assertEqual(tx.state, 'pending')

    @mute_logger('odoo.addons.payment_xpago.controllers.main')
    def test_return_reads_back_the_payment(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, provider_reference=self.checkout_id)
        url = self._build_url(const.PAYMENT_RETURN_ROUTE)
        with patch(SEND, return_value=self.payment_data()) as send:
            self._make_http_get_request(url, params={'id': self.checkout_id, 'externalId': tx.reference})
        self._run_processing()
        self.assertEqual(send.call_args.args, ('GET', f'/developer/v1/one-time-payment/{self.checkout_id}'))
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

    def test_api_key_is_sent_and_environment_follows_the_state(self):
        self.provider.is_live = False
        self.assertTrue(self.provider._build_request_url('/x').startswith(const.API_URLS['test']))
        self.provider.is_live = True
        self.assertTrue(self.provider._build_request_url('/x').startswith(const.API_URLS['live']))
        self.assertEqual(self.provider._build_request_headers('GET', '/x', None)['x-api-key'], 'xp_test_key')

    def test_enabling_without_api_key_is_refused(self):
        with self.assertRaises(ValidationError):
            self.provider.write({'xpago_api_key': False, 'is_live': True})


@tagged('post_install', '-at_install')
class TestDepositAccounts(XpagoCommon):

    ACCOUNTS = {'data': [{'id': 'acc-oper', 'name': 'Banorte Operación', 'isDefault': True},
                         {'id': 'acc-fiscal', 'name': 'BBVA Fiscal', 'isDefault': False}]}

    def sync(self, answer=None):
        with patch(SEND, return_value=answer or self.ACCOUNTS):
            self.provider._xpago_sync_bank_accounts()
        return {a.xpago_id: a for a in self.provider.with_context(active_test=False).xpago_bank_account_ids}

    def test_accounts_are_read_updated_and_archived(self):
        accounts = self.sync()
        self.assertEqual(set(accounts), {'acc-oper', 'acc-fiscal'})
        self.assertTrue(accounts['acc-oper'].is_default)
        accounts = self.sync({'data': [{'id': 'acc-oper', 'name': 'Banorte', 'isDefault': True}]})
        self.assertEqual(accounts['acc-oper'].name, 'Banorte')
        self.assertFalse(accounts['acc-fiscal'].active)

    def test_payment_goes_to_its_account(self):
        accounts = self.sync()
        self.provider.xpago_other_bank_account_id = accounts['acc-oper']
        tx = self._create_transaction('redirect', currency_id=self.currency.id)
        self.assertEqual(tx._xpago_prepare_checkout_payload()['bankAccountId'], 'acc-oper')

    def test_archived_account_is_not_sent(self):
        accounts = self.sync()
        self.provider.xpago_other_bank_account_id = accounts['acc-fiscal']
        self.sync({'data': [{'id': 'acc-oper', 'name': 'Banorte', 'isDefault': True}]})
        tx = self._create_transaction('redirect', currency_id=self.currency.id)
        self.assertNotIn('bankAccountId', tx._xpago_prepare_checkout_payload())
