from datetime import date, timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.account_payment.tests.common import AccountPaymentCommon

SEND = 'odoo.addons.xpago.models.payment_provider.PaymentProvider._xpago_make_request'


@tagged('post_install', '-at_install')
class TestDomiciliation(AccountPaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.xpago = cls._prepare_provider('xpago', update_values={'xpago_api_key': 'xpk_test_key'})
        cls.xpago.journal_id = cls.company_data['default_journal_bank']
        cls.partner.write({'email': 'cliente@ejemplo.mx', 'phone': '443 123 4567'})
        # Records already in the database (other companies, demos) stay out of the scheduled charges here.
        cls.env['payment.xpago.domiciliation'].sudo().search([]).write({'state': 'paused'})
        cls.token = cls.env['payment.token'].create({
            'provider_id': cls.xpago.id,
            'payment_method_id': cls.xpago.payment_method_ids[:1].id,
            'partner_id': cls.partner.id,
            'provider_ref': 'pm-1',
            'payment_details': '4242',
        })

    def setUp(self):
        super().setUp()
        self.calls = []

    def make_invoice(self, amount, day='2026-11-05', due=None):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': day,
            'invoice_date_due': due or day,
            'currency_id': self.env.company.currency_id.id,
            'invoice_line_ids': [(0, 0, {'name': 'Servicio', 'quantity': 1, 'price_unit': amount, 'tax_ids': []})],
        })
        move.action_post()
        return move

    def domiciliation(self, **values):
        return self.env['payment.xpago.domiciliation'].create({
            'partner_id': self.partner.id, 'token_id': self.token.id, 'authorized_on': '2026-11-01', **values})

    def fake_send(self, status='paid'):
        def send(provider, method, path, **kwargs):
            self.calls.append((method, path, kwargs.get('json')))
            body = kwargs.get('json') or {}
            return {'id': f'cp-{len(self.calls)}', 'status': status, 'amount': body.get('amount'),
                    'currency': self.env.company.currency_id.name}
        return patch(SEND, autospec=True, side_effect=send)

    def test_charge_now_pays_all_pending_invoices_in_one_charge(self):
        first, second = self.make_invoice(120), self.make_invoice(80.5)
        record = self.domiciliation(schedule='manual')
        self.assertEqual(record.pending_amount, 200.5)
        with self.fake_send():
            record.action_charge_now()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][1], '/v1/saved-cards/pm-1/payments')
        self.assertEqual(self.calls[0][2]['amount'], 200.5)
        self.assertEqual((first | second).mapped('payment_state'), ['in_payment', 'in_payment'] if
                         first.payment_state == 'in_payment' else ['paid', 'paid'])
        record.invalidate_recordset()
        self.assertEqual(record.transaction_count, 1)
        self.assertFalse(record._invoices_to_charge())

    def test_over_the_limit_is_not_charged(self):
        self.make_invoice(500)
        record = self.domiciliation(schedule='manual', max_amount=300)
        with self.fake_send():
            record.action_charge_now()
        self.assertFalse(self.calls)
        self.assertTrue(record.activity_ids)

    def test_declined_card_tells_the_responsible(self):
        self.make_invoice(100)
        record = self.domiciliation(schedule='manual')
        with patch(SEND, side_effect=ValidationError('declined')), self.assertRaises(UserError):
            record.action_charge_now()

    def test_paused_is_not_charged(self):
        self.make_invoice(100)
        record = self.domiciliation(schedule='manual')
        record.action_pause()
        with self.assertRaises(UserError):
            record.action_charge_now()

    def test_card_of_another_customer_is_refused(self):
        with self.assertRaises(ValidationError):
            self.domiciliation(partner_id=self.env['res.partner'].create({'name': 'Otro'}).id)

    def test_monthly_charges_on_the_day_what_was_invoiced_until_then(self):
        before = self.make_invoice(100, day='2026-10-20')  # before the authorization: by hand only
        november = self.make_invoice(150, day='2026-11-10')
        later = self.make_invoice(70, day='2026-11-20')
        record = self.domiciliation(schedule='monthly', month_day=15)
        with freeze_time('2026-11-14'), self.fake_send():
            self.env['payment.xpago.domiciliation']._cron_charge()
        self.assertFalse(self.calls, "Not before the 15th")
        with freeze_time('2026-11-15'), self.fake_send():
            self.env['payment.xpago.domiciliation']._cron_charge()
        self.assertEqual([c[2]['amount'] for c in self.calls], [150])
        self.assertEqual(november.payment_state in ('paid', 'in_payment'), True)
        with freeze_time('2026-11-25'), self.fake_send():
            self.env['payment.xpago.domiciliation']._cron_charge()
        self.assertEqual(len(self.calls), 1, "The invoice of the 20th waits for December")
        with freeze_time('2026-12-15'), self.fake_send():
            self.env['payment.xpago.domiciliation']._cron_charge()
        self.assertEqual([c[2]['amount'] for c in self.calls], [150, 70])
        self.assertEqual(before.payment_state, 'not_paid')
        self.assertTrue(later.payment_state in ('paid', 'in_payment'))

    def test_last_day_of_the_month(self):
        record = self.domiciliation(schedule='monthly', month_day=31)
        self.assertEqual(record._charge_day(date(2027, 2, 10)), date(2027, 2, 28))
        with freeze_time('2026-11-30'):
            record.invalidate_recordset(['next_date'])
            self.assertEqual(record.next_date, date(2026, 11, 30))

    def test_due_charges_each_invoice_on_its_due_date_and_retries(self):
        invoice = self.make_invoice(90, day='2026-11-02', due='2026-11-12')
        self.domiciliation(schedule='due')
        cron = self.env['payment.xpago.domiciliation']._cron_charge
        with freeze_time('2026-11-11'), self.fake_send():
            cron()
        self.assertFalse(self.calls)
        with freeze_time('2026-11-12'), patch(SEND, side_effect=ValidationError('declined')) as send:
            cron()
        self.assertEqual(send.call_count, 1)
        with freeze_time('2026-11-13'), patch(SEND, side_effect=ValidationError('declined')) as send:
            cron()
        self.assertEqual(send.call_count, 0, "Waits two days before trying again")
        with freeze_time('2026-11-14'), self.fake_send():
            cron()
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(invoice.payment_state in ('paid', 'in_payment'))

    def test_manual_is_never_charged_by_itself(self):
        self.make_invoice(100)
        self.domiciliation(schedule='manual')
        with freeze_time('2026-11-30'), self.fake_send():
            self.env['payment.xpago.domiciliation']._cron_charge()
        self.assertFalse(self.calls)

    def test_customer_gets_an_email(self):
        self.make_invoice(100)
        record = self.domiciliation(schedule='manual')
        with self.fake_send():
            record.action_charge_now()
        mails = self.env['mail.mail'].search([('recipient_ids', 'in', self.partner.ids)])
        self.assertTrue(mails.filtered(lambda m: '100' in (m.subject or '')))

    # === SUBSCRIPTIONS === #

    def make_subscription(self, card=None):
        plan = self.env['sale.subscription.plan'].sudo().create({'name': 'Mensual', 'billing_period_value': 1,
                                                          'billing_period_unit': 'month'})
        product = self.env['product.product'].sudo().create({'name': 'Plan', 'type': 'service', 'recurring_invoice': True,
                                                      'list_price': 10})
        order = self.env['sale.order'].sudo().create({
            'partner_id': self.partner.id, 'plan_id': plan.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 1, 'price_unit': 10})],
        })
        order.action_confirm()
        order.payment_token_id = card
        return order

    def test_subscription_mode_puts_the_card_and_pause_takes_it_back(self):
        if 'sale.subscription.plan' not in self.env:
            self.skipTest('sale_subscription is not installed')
        order = self.make_subscription()
        record = self.domiciliation(source='subscription', schedule='manual')
        self.assertEqual(order.payment_token_id, self.token)
        record.action_pause()
        self.assertFalse(order.payment_token_id)
        record.action_resume()
        self.assertEqual(order.payment_token_id, self.token)

    def test_invoices_mode_keeps_the_card_the_customer_saved_on_the_subscription(self):
        if 'sale.subscription.plan' not in self.env:
            self.skipTest('sale_subscription is not installed')
        order = self.make_subscription(card=self.token)
        record = self.domiciliation(source='invoices', schedule='manual')
        self.assertEqual(order.payment_token_id, self.token, 'creating it must not take the card away')
        record.action_pause()
        record.write({'max_amount': 50})
        self.assertEqual(order.payment_token_id, self.token, 'pausing an invoices record must not either')
