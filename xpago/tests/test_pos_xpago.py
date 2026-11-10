from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon

SEND = 'odoo.addons.xpago.models.payment_provider.PaymentProvider._xpago_make_request'


@tagged('post_install', '-at_install')
class TestPosXpago(TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A provider of the test company, like the payment tests prepare theirs.
        cls.provider = cls.env['payment.provider'].sudo().search([('code', '=', 'xpago')], limit=1).copy(
            {'company_id': cls.env.company.id})
        cls.provider.write({'xpago_api_key': 'xpk_test_key', 'state': 'test'})
        cls.method = cls.env['pos.payment.method'].create({
            'name': 'Tarjeta XPago',
            'journal_id': cls.company_data['default_journal_bank'].id,
            'use_payment_terminal': 'xpago',
            'xpago_provider_id': cls.provider.id,
            'xpago_terminal_serial': 'N950-0001',
        })

    def intent(self, status='pending', **extra):
        return {'id': 'pi-1', 'status': status, 'expires_at': '2099-01-01T00:10:00.000Z',
                'terminal_app_url': 'xpago-terminal://charge/pi-1', **extra}

    def approved(self):
        return self.intent('paid', payment={
            'id': 'pay-1', 'operation_code': '123456', 'authorization_code': 'A1B2C3', 'charged_amount': 150.5,
            'installments': 3,
            'card': {'funding': 'CREDIT', 'brand': 'VISA', 'last4': '4242', 'issuer': 'BBVA', 'entry_mode': 'CHIP'},
        })

    def create_charge(self):
        with patch(SEND, return_value=self.intent()) as send:
            view = self.method.xpago_create_charge({'amount': 150.5, 'order_uuid': 'abcdef12-3456'})
        return view, send

    def test_amount_goes_to_the_terminal(self):
        view, send = self.create_charge()
        method, endpoint = send.call_args.args
        body = send.call_args.kwargs['json']
        self.assertEqual((method, endpoint), ('POST', '/v1/terminal-charges'))
        self.assertEqual((body['amount'], body['terminal_serial'], body['currency']), (150.5, 'N950-0001', self.method.company_id.currency_id.name))
        self.assertEqual(send.call_args.kwargs['idempotency_key'], body['reference'])
        self.assertEqual((view['xpago_id'], view['state']), ('pi-1', 'pending'))
        self.assertEqual(view['terminal_app_url'], 'xpago-terminal://charge/pi-1', 'the app link comes from XPago')

    def test_approved_card_comes_back_to_the_order(self):
        view, _send = self.create_charge()
        with patch(SEND, return_value=self.approved()) as send:
            view = self.method.xpago_charge_status(view['id'])
        self.assertEqual(send.call_args.args, ('GET', '/v1/terminal-charges/pi-1'))
        self.assertEqual(view['state'], 'confirmed')
        payment = view['payment']
        self.assertEqual((payment['transaction_id'], payment['card_type']), ('pay-1', 'VISA CREDIT'))
        # Odoo 17 keeps the rest of the card on the receipt info of the payment.
        for text in ('VISA CREDIT •••• 4242', 'BBVA', 'A1B2C3', '123456', '3 months without interest'):
            self.assertIn(text, payment['ticket'])
        charge = self.env['pos.xpago.charge'].browse(view['id'])
        self.assertEqual((charge.terms, charge.charged_amount), (3, 150.5))

    def test_cancel_on_the_terminal(self):
        view, _send = self.create_charge()
        with patch(SEND, return_value={'id': 'pi-1', 'status': 'canceled'}) as send:
            view = self.method.xpago_cancel_charge(view['id'])
        self.assertEqual(send.call_args.args, ('POST', '/v1/terminal-charges/pi-1/cancel'))
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
        boss = self.env['res.users'].create({'name': 'Dueño', 'login': 'dueno-xpos', 'groups_id': [(4, self.env.ref('base.group_user').id)]})
        self.provider.xpago_notify_user_ids = boss
        view, _send = self.create_charge()
        with patch(SEND, return_value=self.approved()):
            self.method.xpago_charge_status(view['id'])
            self.method.xpago_charge_status(view['id'])
        messages = self.env['mail.message'].sudo().search([('notified_partner_ids', 'in', boss.partner_id.ids)])
        self.assertEqual(len(messages), 1)
        self.assertIn('VISA •••• 4242', messages.body)

    def test_disabled_account_does_not_charge(self):
        self.provider.state = 'disabled'
        with self.assertRaises(UserError):
            self.method.xpago_create_charge({'amount': 10})

    def test_deposit_account_of_the_terminal_or_the_cashier(self):
        Account = self.env['payment.xpago.bank.account']
        oper = Account.create({'provider_id': self.provider.id, 'xpago_id': 'acc-oper', 'name': 'Operación'})
        fiscal = Account.create({'provider_id': self.provider.id, 'xpago_id': 'acc-fiscal', 'name': 'Fiscal'})
        self.method.xpago_bank_account_id = oper
        with patch(SEND, return_value=self.intent()) as send:
            self.method.xpago_create_charge({'amount': 10, 'bank_account_id': fiscal.id})
        self.assertEqual(send.call_args.kwargs['json']['deposit_account_id'], 'acc-oper', 'the cashier may not choose')
        self.method.xpago_choose_account = True
        with patch(SEND, return_value=self.intent()) as send:
            view = self.method.xpago_create_charge({'amount': 10, 'bank_account_id': fiscal.id})
        self.assertEqual(send.call_args.kwargs['json']['deposit_account_id'], 'acc-fiscal')
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
            {'id': 'pay-1', 'terminal_charge_id': 'pi-1', 'amount': 150.5, 'charged_amount': 150.5, 'fee_percent': 2.99,
             'status': 'paid', 'created_at': '2026-11-02T18:00:00.000Z', 'operation_code': '123456',
             'card': {'brand': 'VISA', 'last4': '4242'}},
            {'id': 'pay-9', 'amount': 500.0, 'fee_percent': 2.99, 'status': 'paid', 'created_at': '2026-11-02T19:00:00.000Z'},
        ], 'next_cursor': None}
        wizard = self.env['pos.xpago.reconcile'].create({'provider_id': self.provider.id})
        with patch(SEND, return_value=payments) as send:
            wizard.action_reconcile()
        self.assertEqual(send.call_args.args, ('GET', '/v1/payments'))
        self.assertEqual(send.call_args.kwargs['params']['status'], ['paid', 'refunded'])
        lines = {line.operation_code or line.xpago_amount: line for line in wizard.line_ids}
        ok = lines['123456']
        self.assertEqual((ok.status, ok.charge_id, ok.fee_amount, ok.fee_vat), ('ok', charge, 4.5, 0.72))
        self.assertEqual(lines[500.0].status, 'xpago_only')

    def test_terminal_fields_reach_the_point_of_sale(self):
        self.config = self.basic_config
        self.config.write({'payment_method_ids': [(4, self.method.id)]})
        self.open_new_session()
        Account = self.env['payment.xpago.bank.account']
        account = Account.create({'provider_id': self.provider.id, 'xpago_id': 'acc-pos', 'name': 'Caja'})
        Account.create({'provider_id': self.provider.id, 'xpago_id': 'acc-old', 'name': 'Vieja', 'active': False})
        data = self.pos_session.load_pos_data()
        method = next(m for m in data['pos.payment.method'] if m['id'] == self.method.id)
        self.assertIn('xpago_choose_account', method)
        self.assertEqual([a['id'] for a in data['payment.xpago.bank.account']], account.ids)

    def test_paid_order_keeps_the_card(self):
        self.config = self.basic_config
        self.config.write({'payment_method_ids': [(4, self.method.id)]})
        self.open_new_session()
        product = self.create_product('Anillo', self.categ_basic, 150.5)
        charge = self.paid_charge()
        data = self.create_ui_order_data([(product, 1)], payments=[(self.method, 150.5)])
        data['data']['statement_ids'][0][2].update(charge._xpago_payment_values())
        order = self.env['pos.order'].browse(self.env['pos.order'].create_from_ui([data])[0]['id'])
        self.assertEqual(order.payment_ids.transaction_id, 'pay-1')
        self.assertIn('•••• 4242', order.payment_ids.ticket)
        self.assertEqual((charge.sale_order_id, charge.without_sale), (order, False))

    def test_card_voucher_in_the_receipt_settings(self):
        config = self.env['pos.config'].create({'name': 'Caja voucher'})
        self.assertTrue(config.xpago_voucher_on_receipt, 'on by default')
        self.assertTrue(config.xpago_voucher_signature)
        self.assertFalse(config.xpago_voucher_merchant)
        self.assertIn('pagaré', config.xpago_voucher_credit_text)
        self.assertIn('Autorizo que se cargue a mi cuenta', config.xpago_voucher_debit_text)
        settings = self.env['res.config.settings'].create({'pos_config_id': config.id})
        self.assertTrue(settings.pos_xpago_voucher_on_receipt)
        settings.write({'pos_xpago_voucher_merchant': '1234567', 'pos_xpago_voucher_signature': False,
                        'pos_xpago_voucher_debit_text': 'Débito'})
        settings.execute()
        self.assertEqual((config.xpago_voucher_merchant, config.xpago_voucher_signature, config.xpago_voucher_debit_text),
                         ('1234567', False, 'Débito'))

    def test_card_voucher_reaches_the_receipt(self):
        self.config = self.basic_config
        self.config.write({'payment_method_ids': [(4, self.method.id)], 'xpago_voucher_merchant': '7654321'})
        self.open_new_session()
        data = self.pos_session.load_pos_data()
        self.assertEqual((data['pos.config']['xpago_voucher_on_receipt'], data['pos.config']['xpago_voucher_merchant']),
                         (True, '7654321'))
        product = self.create_product('Anillo', self.categ_basic, 150.5)
        charge = self.paid_charge()
        values = charge._xpago_payment_values()
        self.assertEqual(
            (values['xpago_card_brand'], values['xpago_card_no'], values['xpago_issuer_bank'], values['xpago_authorization'],
             values['xpago_reference'], values['xpago_entry_mode'], values['xpago_terms']),
            ('VISA', '4242', 'BBVA', 'A1B2C3', '123456', 'CHIP', 3))
        ui_order = self.create_ui_order_data([(product, 1)], payments=[(self.method, 150.5)])
        ui_order['data']['statement_ids'][0][2].update(values)
        order = self.env['pos.order'].browse(self.env['pos.order'].create_from_ui([ui_order])[0]['id'])
        payment = order.payment_ids
        self.assertEqual((payment.xpago_card_no, payment.xpago_authorization, payment.xpago_reference, payment.xpago_terms),
                         ('4242', 'A1B2C3', '123456', 3))
        # A receipt printed again (orders list) reads the card back.
        exported = order.export_for_ui()[0]['statement_ids'][0][2]
        self.assertEqual((exported['xpago_card_brand'], exported['xpago_issuer_bank'], exported['xpago_entry_mode']),
                         ('VISA', 'BBVA', 'CHIP'))

    def refund_order(self, charge):
        """A paid sale with the charge's card payment, ready to be refunded."""
        self.basic_config.open_ui()
        order = self.env['pos.order'].create({
            'session_id': self.basic_config.current_session_id.id, 'amount_tax': 0, 'amount_total': charge.amount,
            'amount_paid': 0, 'amount_return': 0, 'lines': [],
        })
        order.add_payment({'amount': charge.amount, 'payment_method_id': self.method.id, 'pos_order_id': order.id,
                           'payment_status': 'done', **charge._xpago_payment_values()})
        return order

    def test_refund_order_gives_the_card_payment_back(self):
        self.basic_config.payment_method_ids |= self.method
        charge = self.paid_charge()
        order = self.refund_order(charge)
        with patch(SEND, return_value={'id': 'pi-1', 'status': 'refunded'}) as send:
            result = self.method.xpago_refund_charge({'amount': -150.5, 'refunded_order_ids': order.ids})
        self.assertEqual(send.call_args.args, ('POST', '/v1/terminal-charges/pi-1/refund'))
        self.assertEqual((charge.state, result['payment']['xpago_card_no']), ('refunded', '4242'))

    def test_refund_is_in_full_only(self):
        self.basic_config.payment_method_ids |= self.method
        charge = self.paid_charge()
        order = self.refund_order(charge)
        with patch(SEND) as send, self.assertRaises(UserError):
            self.method.xpago_refund_charge({'amount': -50, 'refunded_order_ids': order.ids})
        send.assert_not_called()
        self.assertEqual(charge.state, 'confirmed')

    def test_refund_after_the_day_tells_the_cashier(self):
        self.basic_config.payment_method_ids |= self.method
        charge = self.paid_charge()
        order = self.refund_order(charge)
        with patch(SEND, side_effect=ValidationError('The refund window expired.')), self.assertRaises(UserError):
            self.method.xpago_refund_charge({'amount': -150.5, 'refunded_order_ids': order.ids})
        self.assertEqual(charge.state, 'confirmed')

    def test_refund_the_fee_does_not_cover_waits_on_the_terminal(self):
        self.basic_config.payment_method_ids |= self.method
        charge = self.paid_charge()
        order = self.refund_order(charge)
        refused = ValidationError('The fee is not covered.')
        refused.xpago_code = 'refund_fee_not_covered'

        def processor(method, endpoint, **kwargs):
            if method == 'POST':
                raise refused
            return self.approved()
        with patch(SEND, side_effect=processor):
            result = self.method.xpago_refund_charge({'amount': -150.5, 'refunded_order_ids': order.ids})
        self.assertTrue(result['wait_on_terminal'])
        self.assertEqual((result['charge_id'], charge.state), (charge.id, 'confirmed'))
        with patch(SEND, return_value=self.approved()):
            self.assertEqual(self.method.xpago_refund_status({'charge_id': charge.id}), {'state': 'confirmed'})
        with patch(SEND, return_value={**self.approved(), 'status': 'refunded'}):
            status = self.method.xpago_refund_status({'charge_id': charge.id})
        self.assertEqual((status['state'], status['payment']['xpago_card_no'], charge.state), ('refunded', '4242', 'refunded'))

    def test_other_refusals_still_tell_the_cashier(self):
        self.basic_config.payment_method_ids |= self.method
        charge = self.paid_charge()
        order = self.refund_order(charge)
        declined = ValidationError('The bank did not accept the refund.')
        declined.xpago_code = 'refund_declined'

        def processor(method, endpoint, **kwargs):
            if method == 'POST':
                raise declined
            return self.approved()
        with patch(SEND, side_effect=processor), self.assertRaises(UserError):
            self.method.xpago_refund_charge({'amount': -150.5, 'refunded_order_ids': order.ids})
        self.assertEqual(charge.state, 'confirmed')

    def test_refund_made_on_the_terminal_links_to_one_refund_order(self):
        self.basic_config.payment_method_ids |= self.method
        charge = self.paid_charge()
        order = self.refund_order(charge)
        with patch(SEND, return_value={**self.approved(), 'status': 'refunded'}):
            self.env['pos.xpago.charge']._xpago_cron_refresh()
        self.assertEqual(charge.state, 'refunded', 'the scheduled action reads the paid charges of the day')
        with patch(SEND) as send:
            result = self.method.xpago_refund_charge({'amount': -150.5, 'refunded_order_ids': order.ids})
        send.assert_not_called()
        self.assertEqual((result['state'], result['payment']['xpago_card_no']), ('refunded', '4242'))
        self.env['pos.payment'].create({
            'pos_order_id': order.id, 'payment_method_id': self.method.id, 'amount': -150.5,
            'transaction_id': charge.payment_id})
        with patch(SEND), self.assertRaises(UserError):
            self.method.xpago_refund_charge({'amount': -150.5, 'refunded_order_ids': order.ids})

    def test_refund_refusals_in_words_the_cashier_acts_on(self):
        class Answer:
            def __init__(self, body):
                self.body = body

            def json(self):
                return self.body
        refusal = self.provider._xpago_known_refusal(Answer({'error': {
            'code': 'refund_fee_not_covered', 'details': {'required': 3.48, 'missing': 2.28}}}))
        self.assertIn('3.48', refusal)
        self.assertIn('2.28', refusal)
        self.assertEqual(self.provider._xpago_error_code(Answer({'error': {'code': 'refund_declined'}})), 'refund_declined')
        self.assertIsNone(self.provider._xpago_known_refusal(Answer({'error': {'code': 'not_found'}})))

    def test_back_office_refund(self):
        charge = self.paid_charge()
        with patch(SEND, return_value={'id': 'pi-1', 'status': 'refunded'}) as send:
            charge.action_xpago_refund()
        self.assertEqual(send.call_args.args, ('POST', '/v1/terminal-charges/pi-1/refund'))
        self.assertEqual(charge.state, 'refunded')
        self.assertFalse(charge.without_sale, 'a refunded charge is not a missing sale')

    def test_settings_ask_to_connect_a_terminal_account_without_xpago_key(self):
        settings = self.env['res.config.settings'].create({'pos_config_id': self.basic_config.id})
        self.assertFalse(settings.xpago_needs_connect)
        self.provider.state = 'disabled'
        self.env.cr.execute("UPDATE payment_provider SET xpago_api_key = 'old-processor-key' WHERE id = %s", [self.provider.id])
        self.provider.invalidate_recordset()
        settings = self.env['res.config.settings'].create({'pos_config_id': self.basic_config.id})
        self.assertTrue(settings.xpago_needs_connect, 'the terminal uses it even if it is disabled online')
        self.assertEqual(settings.action_xpago_connect()['type'], 'ir.actions.act_url')
