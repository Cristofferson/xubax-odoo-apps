from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon

SEND = 'odoo.addons.payment.models.payment_provider.PaymentProvider._send_api_request'


@tagged('post_install', '-at_install')
class TestPosXpago(TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env['payment.provider'].search([('code', '=', 'xpago')], limit=1)
        cls.provider.write({'xpago_api_key': 'xp_test_key', 'is_live': False, 'company_id': cls.env.company.id})
        cls.method = cls.env['pos.payment.method'].create({
            'name': 'Tarjeta XPago',
            'type': 'bank',
            'journal_id': cls.company_data['default_journal_bank'].id,
            'payment_method_type': 'terminal',
            'payment_provider': 'xpago',
            'xpago_provider_id': cls.provider.id,
            'xpago_terminal_serial': 'N950-0001',
        })

    def intent(self, status='PENDING', **extra):
        return {'id': 'pi-1', 'status': status, 'expired': False, 'expiresAt': '2099-01-01T00:10:00.000Z', **extra}

    def approved(self):
        return self.intent('CONFIRMED', paymentSummary={
            'status': 'SUCCESS',
            'payment': {'id': 'pay-1', 'operationCode': 123456, 'chargedAmount': 150.5, 'terms': 3},
            'paymentTransaction': {'resultCode': 'A1B2C3'},
            'cardInformation': {'fundingSource': 'CREDIT', 'networkType': 'VISA', 'lastFourDigits': '4242',
                                'issuingBank': 'BBVA', 'entryMode': 'CHIP'},
        })

    def create_charge(self):
        with patch(SEND, return_value=self.intent()) as send:
            view = self.method.xpago_create_charge({'amount': 150.5, 'order_uuid': 'abcdef12-3456'})
        return view, send

    def test_amount_goes_to_the_terminal(self):
        view, send = self.create_charge()
        method, endpoint = send.call_args.args
        body = send.call_args.kwargs['json']
        self.assertEqual((method, endpoint), ('POST', '/payment-intent'))
        self.assertEqual((body['amount'], body['terminalCode'], body['currency']), (150.5, 'N950-0001', self.method.company_id.currency_id.name))
        self.assertEqual((view['xpago_id'], view['state']), ('pi-1', 'pending'))

    def test_approved_card_comes_back_to_the_order(self):
        view, _send = self.create_charge()
        with patch(SEND, return_value=self.approved()) as send:
            view = self.method.xpago_charge_status(view['id'])
        self.assertEqual(send.call_args.args, ('GET', '/payment-intent/pi-1'))
        self.assertEqual(view['state'], 'confirmed')
        self.assertEqual(view['payment']['card_no'], '4242')
        self.assertEqual(view['payment']['payment_ref_no'], '123456')
        charge = self.env['pos.xpago.charge'].browse(view['id'])
        self.assertEqual((charge.terms, charge.charged_amount), (3, 150.5))

    def test_cancel_on_the_terminal(self):
        view, _send = self.create_charge()
        with patch(SEND, return_value=self.intent('CANCELLED')) as send:
            view = self.method.xpago_cancel_charge(view['id'])
        self.assertEqual(send.call_args.args, ('POST', '/payment-intent/pi-1/cancel'))
        self.assertEqual(view['state'], 'cancelled')

    def test_card_approved_before_the_cancel_stays_paid(self):
        view, _send = self.create_charge()
        with patch(SEND, side_effect=[ValidationError('409'), self.approved()]):
            view = self.method.xpago_cancel_charge(view['id'])
        self.assertEqual(view['state'], 'confirmed')

    def test_refused_charge_tells_the_cashier(self):
        with patch(SEND, side_effect=ValidationError('terminal not found')), self.assertRaises(UserError):
            self.method.xpago_create_charge({'amount': 10})

    def test_negative_amount_is_refused(self):
        with self.assertRaises(UserError):
            self.method.xpago_create_charge({'amount': -5})

    def test_paid_charge_notifies_once(self):
        boss = self.env['res.users'].create({'name': 'Dueño', 'login': 'dueno-xpos', 'group_ids': [(4, self.env.ref('base.group_user').id)]})
        self.provider.xpago_notify_user_ids = boss
        view, _send = self.create_charge()
        with patch(SEND, return_value=self.approved()):
            self.method.xpago_charge_status(view['id'])
            self.method.xpago_charge_status(view['id'])
        messages = self.env['mail.message'].sudo().search([('notified_partner_ids', 'in', boss.partner_id.ids)])
        self.assertEqual(len(messages), 1)
        self.assertIn('VISA •••• 4242', messages.body)

    def test_disabled_account_does_not_charge(self):
        self.provider.active = False
        with self.assertRaises(UserError):
            self.method.xpago_create_charge({'amount': 10})

    def test_deposit_account_of_the_terminal_or_the_cashier(self):
        Account = self.env['payment.xpago.bank.account']
        oper = Account.create({'provider_id': self.provider.id, 'xpago_id': 'acc-oper', 'name': 'Operación'})
        fiscal = Account.create({'provider_id': self.provider.id, 'xpago_id': 'acc-fiscal', 'name': 'Fiscal'})
        self.method.xpago_bank_account_id = oper
        with patch(SEND, return_value=self.intent()) as send:
            self.method.xpago_create_charge({'amount': 10, 'bank_account_id': fiscal.id})
        self.assertEqual(send.call_args.kwargs['json']['bankAccountId'], 'acc-oper', 'the cashier may not choose')
        self.method.xpago_choose_account = True
        with patch(SEND, return_value=self.intent()) as send:
            view = self.method.xpago_create_charge({'amount': 10, 'bank_account_id': fiscal.id})
        self.assertEqual(send.call_args.kwargs['json']['bankAccountId'], 'acc-fiscal')
        self.assertEqual(self.env['pos.xpago.charge'].browse(view['id']).bank_account_id, fiscal)

    def paid_charge(self):
        view, _send = self.create_charge()
        with patch(SEND, return_value=self.approved()):
            self.method.xpago_charge_status(view['id'])
        return self.env['pos.xpago.charge'].browse(view['id'])

    def test_paid_charge_without_order_is_found(self):
        charge = self.paid_charge()
        Charge = self.env['pos.xpago.charge']
        self.assertTrue(charge.without_sale)
        self.assertNotIn(charge, Charge.search([('without_sale', '=', True)]), 'still on the cashier screen')
        self.env.cr.execute("UPDATE pos_xpago_charge SET create_date = create_date - interval '30 minutes' WHERE id = %s", [charge.id])
        charge.invalidate_recordset()
        self.assertIn(charge, Charge.search([('without_sale', '=', True)]))

    def test_reconciliation_matches_fees_and_flags_problems(self):
        charge = self.paid_charge()
        payments = {'data': [
            {'id': 'pay-1', 'paymentIntentId': 'pi-1', 'amount': 150.5, 'chargedAmount': 150.5, 'fee': 2.99, 'status': 'CONFIRMED',
             'createdAt': '2026-11-02T18:00:00.000Z', 'operationCode': 123456, 'card': {'network': 'VISA', 'lastFourDigits': '4242'}},
            {'id': 'pay-9', 'amount': 500.0, 'fee': 2.99, 'status': 'CONFIRMED', 'createdAt': '2026-11-02T19:00:00.000Z'},
        ], 'pagination': {}}
        wizard = self.env['pos.xpago.reconcile'].create({'provider_id': self.provider.id})
        with patch(SEND, return_value=payments):
            wizard.action_reconcile()
        lines = {line.operation_code or line.xpago_amount: line for line in wizard.line_ids}
        ok = lines['123456']
        self.assertEqual((ok.status, ok.charge_id, ok.fee_amount, ok.fee_vat), ('ok', charge, 4.5, 0.72))
        self.assertEqual(lines[500.0].status, 'xpago_only')

    def test_point_of_sale_loads_the_accounts_of_its_terminals(self):
        Account = self.env['payment.xpago.bank.account']
        mine = Account.create({'provider_id': self.provider.id, 'xpago_id': 'acc-pos', 'name': 'Caja'})
        config = self.basic_config
        config.payment_method_ids = [(4, self.method.id)]
        domain = Account._load_pos_data_domain({'pos.config': config})
        self.assertIn(mine, Account.search(domain))
        self.assertIn('payment.xpago.bank.account', self.env['pos.session']._load_pos_data_models(config))
