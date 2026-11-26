from datetime import timedelta
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
            'payment_method_type': 'terminal',
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

    def test_printing_on_the_terminal_leaves_the_voucher_to_it(self):
        _view, send = self.create_charge()
        self.assertNotIn('print_voucher', send.call_args.kwargs['json'], 'by default the terminal prints its voucher')
        self.config = self.basic_config
        self.config.payment_method_ids = [(4, self.method.id)]
        self.config.xpago_print_on_terminal = True
        session = self.open_new_session()
        with patch(SEND, return_value=self.intent()) as send:
            self.method.xpago_create_charge({'amount': 10.0, 'order_uuid': 'abcdef12-3456', 'session_id': session.id})
        self.assertIs(send.call_args.kwargs['json']['print_voucher'], False)

    def _session_with(self, **config_values):
        self.config = self.basic_config
        self.config.payment_method_ids = [(4, self.method.id)]
        self.config.write(config_values)
        return self.open_new_session()

    def test_tip_from_the_till_goes_apart_and_the_terminal_does_not_ask(self):
        session = self._session_with(xpago_tip_mode='terminal')
        self.assertTrue(self.config.iface_tipproduct, 'a tip mode turns on the tip product')
        with patch(SEND, return_value=self.intent()) as send:
            self.method.xpago_create_charge({'amount': 285.0, 'tip_amount': 30.0, 'order_uuid': 'abcdef12-3456',
                                             'session_id': session.id})
        body = send.call_args.kwargs['json']
        self.assertEqual((body['amount'], body['tip_amount']), (285.0, 30.0))
        self.assertNotIn('collect_tip', body)

    def test_the_terminal_asks_for_the_tip_only_when_set(self):
        session = self._session_with(xpago_tip_mode='terminal')
        with patch(SEND, return_value=self.intent()) as send:
            self.method.xpago_create_charge({'amount': 1000.0, 'order_uuid': 'abcdef12-3456', 'session_id': session.id})
        self.assertIs(send.call_args.kwargs['json']['collect_tip'], True)
        with patch(SEND, return_value=self.intent()) as send:
            self.method.xpago_create_charge({'amount': 500.0, 'order_uuid': 'abcdef12-3456', 'session_id': session.id,
                                             'ask_tip': False})
        self.assertNotIn('collect_tip', send.call_args.kwargs['json'], 'second part of a split sale')
        self.config.xpago_tip_mode = 'cashier'
        with patch(SEND, return_value=self.intent()) as send:
            self.method.xpago_create_charge({'amount': 1000.0, 'order_uuid': 'abcdef12-3456', 'session_id': session.id})
        self.assertNotIn('collect_tip', send.call_args.kwargs['json'])

    def test_months_go_to_the_terminal(self):
        with patch(SEND, return_value=self.intent()) as send:
            self.method.xpago_create_charge({'amount': 3000.0, 'order_uuid': 'abcdef12-3456', 'terms': [6, 1, 3, 3]})
        self.assertEqual(send.call_args.kwargs['json']['installments'], [1, 3, 6])
        with patch(SEND, return_value=self.intent()) as send:
            self.method.xpago_create_charge({'amount': 3000.0, 'order_uuid': 'abcdef12-3456', 'terms': False})
        self.assertNotIn('installments', send.call_args.kwargs['json'], 'no rule: the terminal offers its plans')

    def test_tip_chosen_on_the_terminal_comes_back(self):
        view, _send = self.create_charge()
        paid = self.approved()
        paid['payment'].update({'tip_amount': 150.0, 'charged_amount': 1150.0})
        with patch(SEND, return_value=paid):
            view = self.method.xpago_charge_status(view['id'])
        self.assertEqual((view['tip_amount'], view['charged_amount']), (150.0, 1150.0))

    def test_approved_card_comes_back_to_the_order(self):
        view, _send = self.create_charge()
        with patch(SEND, return_value=self.approved()) as send:
            view = self.method.xpago_charge_status(view['id'])
        self.assertEqual(send.call_args.args, ('GET', '/v1/terminal-charges/pi-1'))
        self.assertEqual(view['state'], 'confirmed')
        self.assertEqual(view['payment']['card_no'], '4242')
        self.assertEqual(view['payment']['payment_method_authcode'], 'A1B2C3')
        self.assertEqual(view['payment']['payment_ref_no'], '123456')
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
        self.provider.state = 'disabled'
        with self.assertRaises(UserError):
            self.method.xpago_create_charge({'amount': 10})

    def test_deposit_account_chosen_by_the_cashier(self):
        Account = self.env['payment.xpago.bank.account']
        fiscal = Account.create({'provider_id': self.provider.id, 'xpago_id': 'acc-fiscal', 'name': 'Fiscal'})
        with patch(SEND, return_value=self.intent()) as send:
            self.method.xpago_create_charge({'amount': 10, 'bank_account_id': fiscal.id})
        self.assertNotIn('deposit_account_id', send.call_args.kwargs['json'], 'the cashier may not choose')
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
        deposits = {'data': [
            {'id': 'po-0', 'status': 'returned', 'tracking_key': 'OLD'},
            {'id': 'po-1', 'status': 'paid', 'tracking_key': 'CMPG2026110300001', 'paid_at': '2026-11-03T15:01:00.000Z'},
        ], 'next_cursor': None}
        deposit_lines = {
            'po-0': {'data': [{'type': 'payment', 'payment_id': 'pay-1', 'net': 145.0, 'fee': 4.5, 'tax': 0.72}]},
            'po-1': {'data': [{'type': 'payment', 'payment_id': 'pay-1', 'amount': 150.5, 'fee': 3.9, 'tax': 0.62,
                               'net': 145.98}, {'type': 'balance_recovery', 'net': -20}]},
        }
        calls = []

        def answer(method, endpoint, **kwargs):
            calls.append((endpoint, kwargs.get('params')))
            if endpoint == '/v1/payments':
                return payments
            if endpoint == '/v1/deposits':
                return deposits
            return deposit_lines[endpoint.split('/')[3]]

        wizard = self.env['pos.xpago.reconcile'].create({'provider_id': self.provider.id})
        with patch(SEND, side_effect=answer):
            wizard.action_reconcile()
        self.assertEqual(calls[0][0], '/v1/payments')
        self.assertEqual(calls[0][1]['status'], ['paid', 'refunded'])
        self.assertEqual([c[0] for c in calls[1:]], ['/v1/deposits', '/v1/deposits/po-0/lines', '/v1/deposits/po-1/lines'])
        lines = {line.operation_code or line.xpago_amount: line for line in wizard.line_ids}
        ok = lines['123456']
        self.assertEqual((ok.status, ok.charge_id), ('ok', charge))
        # The paid deposit wins over the returned attempt, and its real fee over the one estimated from the rate.
        self.assertEqual((ok.deposit_status, ok.deposit_tracking_key, ok.net_amount, ok.fee_amount, ok.fee_vat),
                         ('paid', 'CMPG2026110300001', 145.98, 3.9, 0.62))
        self.assertTrue(ok.deposit_date)
        self.assertEqual(lines[500.0].deposit_status, 'pending', 'paid and in no deposit yet')
        self.assertEqual(lines[500.0].status, 'xpago_only')

    def test_reconciliation_runs_without_deposits(self):
        """An XPago that does not know deposits yet: the reconciliation still runs, with the fee from the rate."""
        self.paid_charge()
        payments = {'data': [{'id': 'pay-1', 'terminal_charge_id': 'pi-1', 'amount': 150.5, 'charged_amount': 150.5,
                              'fee_percent': 2.99, 'status': 'paid', 'created_at': '2026-11-02T18:00:00.000Z',
                              'operation_code': '123456'}], 'next_cursor': None}

        def answer(method, endpoint, **kwargs):
            if endpoint == '/v1/payments':
                return payments
            raise ValidationError('not_found')

        wizard = self.env['pos.xpago.reconcile'].create({'provider_id': self.provider.id})
        with patch(SEND, side_effect=answer):
            wizard.action_reconcile()
        line = wizard.line_ids
        self.assertEqual((line.fee_amount, line.fee_vat, line.deposit_status), (4.5, 0.72, 'pending'))

    def test_card_voucher_in_the_receipt(self):
        config = self.env['pos.config'].create({'name': 'Caja voucher'})
        # On by default, with the Mexican legends and the signature line.
        self.assertTrue(config.xpago_voucher_on_receipt)
        self.assertTrue(config.xpago_voucher_signature)
        self.assertFalse(config.xpago_voucher_merchant)
        self.assertIn('pagaré', config.xpago_voucher_credit_text)
        self.assertIn('Autorizo', config.xpago_voucher_debit_text)
        # The point of sale reads the settings with the rest of its configuration.
        loaded = config._load_pos_data_fields(config.id)
        self.assertTrue(not loaded or 'xpago_voucher_on_receipt' in loaded)
        # Edited from the point of sale settings.
        settings = self.env['res.config.settings'].create({'pos_config_id': config.id})
        self.assertTrue(settings.pos_xpago_voucher_on_receipt)
        settings.write({
            'pos_xpago_voucher_on_receipt': False,
            'pos_xpago_voucher_merchant': '1234567',
            'pos_xpago_voucher_debit_text': 'Cargo autorizado.',
            'pos_xpago_voucher_signature': False,
        })
        settings.execute()
        self.assertFalse(config.xpago_voucher_on_receipt)
        self.assertEqual(config.xpago_voucher_merchant, '1234567')
        self.assertEqual(config.xpago_voucher_debit_text, 'Cargo autorizado.')
        self.assertFalse(config.xpago_voucher_signature)

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
        self.assertEqual((charge.state, result['payment']['card_no']), ('refunded', '4242'))

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
        self.assertEqual((status['state'], status['payment']['card_no'], charge.state), ('refunded', '4242', 'refunded'))

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
            self.env['pos.xpago.charge'].sudo()._xpago_cron_refresh()
        self.assertEqual(charge.state, 'refunded', 'the scheduled action reads the paid charges of the day')
        with patch(SEND) as send:
            result = self.method.xpago_refund_charge({'amount': -150.5, 'refunded_order_ids': order.ids})
        send.assert_not_called()
        self.assertEqual((result['state'], result['payment']['card_no']), ('refunded', '4242'))
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

    def test_cashier_chooses_the_months(self):
        """«The cashier chooses the months»: set per register in the settings, with the months of the account; the
        one plan the cashier picks goes alone to the terminal, so it offers the customer nothing to choose."""
        settings = self.env['res.config.settings'].create({'pos_config_id': self.basic_config.id})
        self.assertFalse(settings.pos_xpago_cashier_terms)
        self.assertEqual(settings.pos_xpago_terms_offered, '3, 6, 9, 12')
        settings.write({'pos_xpago_cashier_terms': True, 'pos_xpago_terms_offered': '3, 6'})
        settings.execute()
        self.assertTrue(self.basic_config.xpago_cashier_terms)
        with self.assertRaises(ValidationError):
            self.basic_config.xpago_terms_offered = '3, seis'
        with patch(SEND, return_value=self.intent()) as send:
            self.method.xpago_create_charge({'amount': 600.0, 'order_uuid': 'abcdef12-3456', 'terms': [6]})
        self.assertEqual(send.call_args.kwargs['json']['installments'], [6])
        charge = self.env['pos.xpago.charge'].sudo().search([], order='id desc', limit=1)
        charge.terms = 6
        self.assertEqual(charge._xpago_payment_values()['xpago_terms'], 6, 'the months go to the payment and its voucher')

    # «Force done» asks XPago first: a charge cancelled on the terminal never closes a sale as paid.

    def force_check(self, status_answer, amount=150.5, uuid='abcdef12-3456'):
        self.create_charge()
        with patch(SEND, return_value=status_answer):
            return self.method.xpago_force_check({'order_uuid': uuid, 'amount': amount})

    def test_force_done_cancelled_on_the_terminal_is_not_paid(self):
        self.assertEqual(self.force_check(self.intent('canceled'))['state'], 'cancelled')

    def test_force_done_still_waiting(self):
        self.assertEqual(self.force_check(self.intent())['state'], 'pending')

    def test_force_done_without_a_charge_of_this_sale(self):
        self.assertEqual(self.force_check(self.approved(), uuid='other-uuid')['state'], 'none')

    def test_force_done_approved_gives_the_card(self):
        view = self.force_check(self.approved())
        self.assertEqual(view['state'], 'confirmed')
        self.assertEqual((view['payment']['transaction_id'], view['payment']['card_no']), ('pay-1', '4242'))

    def test_force_done_approved_charge_of_another_amount(self):
        self.assertEqual(self.force_check(self.approved(), amount=999.0)['state'], 'unmatched')

    def test_retry_takes_the_approved_charge_of_the_sale(self):
        """«Retry» after the register gave up on a card approved after all (LAMUR 20-nov, $990): the approved charge pays
        the sale and nothing goes to the terminal again; once a payment uses it, «Retry» charges anew."""
        self.force_check(self.approved())
        with patch(SEND) as send:
            view = self.method.xpago_create_charge({'amount': 150.5, 'order_uuid': 'abcdef12-3456'})
        send.assert_not_called()
        self.assertEqual((view['state'], view['payment']['transaction_id']), ('confirmed', 'pay-1'))
        with patch(SEND, return_value=self.intent()) as send:
            self.method.xpago_create_charge({'amount': 99.0, 'order_uuid': 'abcdef12-3456'})
        send.assert_called_once()

    def test_second_card_of_the_same_amount_is_a_new_charge(self):
        """Two cards of the same amount in one sale (LAMUR 24-nov: $1 + $1): the sale is not saved yet, so Odoo sees no
        payment using the first card. The register says which payments its other lines hold; the second card goes to
        the terminal as a charge of its own instead of getting the first card's approved charge back (one voucher
        printed twice, the second card never charged)."""
        self.force_check(self.approved())
        with patch(SEND, return_value=dict(self.intent(), id='pi-2')) as send:
            view = self.method.xpago_create_charge({'amount': 150.5, 'order_uuid': 'abcdef12-3456',
                                                    'taken_payment_ids': ['pay-1']})
        self.assertIn(('POST', '/v1/terminal-charges'), [c.args for c in send.call_args_list])
        self.assertEqual((view['state'], view['xpago_id']), ('pending', 'pi-2'))
        with patch(SEND, return_value=self.approved()):
            forced = self.method.xpago_force_check({'order_uuid': 'abcdef12-3456', 'amount': 150.5,
                                                    'taken_payment_ids': ['pay-1']})
        self.assertNotEqual(forced.get('payment', {}).get('transaction_id'), 'pay-1',
                            '«Force done» on the second card never hands over the first card')

    def test_months_by_amount_bound_the_terminal(self):
        """«Months without interest by amount» of the provider bound the terminal as they bound the online checkout
        (E2E 23-nov: a $150 charge went out with every plan of the account)."""
        self.provider.xpago_installment_rule_ids = [(0, 0, {'min_amount': 1000, 'terms': '3, 6'})]
        with patch(SEND, return_value=self.intent()) as send:
            self.method.xpago_create_charge({'amount': 150.5, 'order_uuid': 'months-1'})
        self.assertEqual(send.call_args.kwargs['json']['installments'], [1])
        with patch(SEND, return_value=dict(self.intent(), id='pi-2')) as send:
            self.method.xpago_create_charge({'amount': 2000.0, 'order_uuid': 'months-2', 'terms': [6]})
        self.assertEqual(send.call_args.kwargs['json']['installments'], [6])

    def test_retry_after_reload_never_charges_twice(self):
        """The register reloaded while waiting and the card was approved after (E2E 22-nov): Odoo still has the charge
        as waiting. «Retry» asks XPago first and takes the approved charge; nothing new goes to the terminal."""
        self.create_charge()
        with patch(SEND, return_value=self.approved()) as send:
            view = self.method.xpago_create_charge({'amount': 150.5, 'order_uuid': 'abcdef12-3456'})
        self.assertNotIn('/v1/terminal-charges', [c.args[1] for c in send.call_args_list if c.args[0] == 'POST'])
        self.assertEqual((view['state'], view['payment']['transaction_id']), ('confirmed', 'pay-1'))

    def test_retry_cancels_the_charge_still_waiting(self):
        """A charge of the sale still waiting on the terminal is cancelled before the new one: never two alive."""
        first, _send = self.create_charge()
        answers = [self.intent(), {'data': []}, self.intent('canceled'), dict(self.intent(), id='pi-2')]
        with patch(SEND, side_effect=answers) as send:
            view = self.method.xpago_create_charge({'amount': 150.5, 'order_uuid': 'abcdef12-3456'})
        posts = [c.args[1] for c in send.call_args_list if c.args[0] == 'POST']
        self.assertEqual(posts, ['/v1/terminal-charges/pi-1/cancel', '/v1/terminal-charges'])
        self.assertEqual(self.env['pos.xpago.charge'].browse(first['id']).state, 'cancelled')
        self.assertNotEqual(view['id'], first['id'])

    def test_cancel_after_reload_cancels_on_the_terminal(self):
        """«Cancel» on a line the reloaded register no longer follows still cancels the charge on the terminal."""
        first, _send = self.create_charge()
        with patch(SEND, side_effect=[self.intent(), {'data': []}, self.intent('canceled')]):
            result = self.method.xpago_cancel_order_charges({'order_uuid': 'abcdef12-3456', 'amount': 150.5})
        self.assertEqual(result['state'], 'cancelled')
        self.assertEqual(self.env['pos.xpago.charge'].browse(first['id']).state, 'cancelled')

    # Without a card in the time of the payment method, the charge is cancelled; a card paid at the end is not.

    def _age(self, seconds):
        charge = self.env['pos.xpago.charge'].search([('payment_method_id', '=', self.method.id)], order='id desc', limit=1)
        self.env.cr.execute("UPDATE pos_xpago_charge SET create_date = now() at time zone 'UTC' - interval '%s seconds' WHERE id = %s",
                            [seconds, charge.id])
        charge.invalidate_recordset()
        return charge

    def test_timeout_default_and_loaded_in_the_register(self):
        self.assertEqual(self.method.xpago_card_timeout, 120)
        self.assertIn('xpago_card_timeout', self.env['pos.payment.method']._load_pos_data_fields(self.basic_config.id))

    def test_timeout_cancels_the_charge(self):
        view, _send = self.create_charge()
        with patch(SEND, side_effect=[self.intent(), {'data': []}, self.intent('canceled')]) as send:
            result = self.method.xpago_timeout_charge(view['id'])
        self.assertEqual(send.call_args_list[-1].args, ('POST', '/v1/terminal-charges/pi-1/cancel'))
        self.assertEqual((result['state'], result['timed_out']), ('cancelled', True))

    def test_timeout_never_cancels_a_card_paid_at_the_last_second(self):
        view, _send = self.create_charge()
        with patch(SEND, return_value=self.approved()) as send:
            result = self.method.xpago_timeout_charge(view['id'])
        self.assertNotIn(('POST', '/v1/terminal-charges/pi-1/cancel'), [c.args for c in send.call_args_list])
        self.assertEqual(result['state'], 'confirmed')
        self.assertFalse(result['timed_out'])

    def test_scheduled_action_cancels_only_late_charges(self):
        self.create_charge()
        charge = self._age(30)
        with patch(SEND, return_value=self.intent()) as send:
            self.env['pos.xpago.charge'].sudo()._xpago_cron_refresh()
        self.assertNotIn(('POST', '/v1/terminal-charges/pi-1/cancel'), [c.args for c in send.call_args_list])
        self.assertEqual(charge.state, 'pending')
        self._age(200)
        with patch(SEND, side_effect=lambda method, endpoint, **kw: self.intent('canceled') if endpoint.endswith('/cancel') else self.intent()):
            self.env['pos.xpago.charge'].sudo()._xpago_cron_refresh()
        self.assertEqual((charge.state, charge.timed_out), ('cancelled', True))

    def test_timeout_zero_waits_for_the_terminal(self):
        self.method.xpago_card_timeout = 0
        self.create_charge()
        charge = self._age(5000)
        with patch(SEND, return_value=self.intent()) as send:
            self.env['pos.xpago.charge'].sudo()._xpago_cron_refresh()
        self.assertNotIn(('POST', '/v1/terminal-charges/pi-1/cancel'), [c.args for c in send.call_args_list])
        self.assertEqual(charge.state, 'pending')

    # A foreign card goes through another acquirer and the processor does not tie its payment to the charge (LAMUR
    # 20-nov, $990): the terminal the payment names says which charge it paid.

    def loose(self, amount=150.5, serial='N950-0001', **extra):
        charge = self.env['pos.xpago.charge'].search([('payment_method_id', '=', self.method.id)], order='id desc', limit=1)
        return {'id': 'pay-loose', 'operation_code': '75971794205', 'status': 'paid', 'channel': 'other',
                'card_present': True, 'amount': amount, 'charged_amount': amount, 'tip_amount': 0, 'installments': 1,
                'created_at': (charge.create_date + timedelta(seconds=40)).isoformat() + 'Z', 'terminal_serial': serial,
                'authorization_code': '06523D', 'card': {'last4': '1065', 'brand': 'UNKNOWN', 'funding': 'CREDIT'},
                **extra}

    def test_notice_of_a_loose_payment_pays_the_charge_of_its_terminal(self):
        self.create_charge()
        charge = self._age(60)
        with patch(SEND, return_value=self.loose()) as send:
            self.provider._xpago_handle_notice({'object': {'kind': 'payment', 'id': 'pay-loose'}})
        self.assertEqual(send.call_args.args, ('GET', '/v1/payments/pay-loose'))
        self.assertEqual((charge.state, charge.payment_id, charge.authorization_code, charge.card_no),
                         ('confirmed', 'pay-loose', '06523D', '1065'))

    def test_a_loose_payment_pays_even_a_charge_cancelled_for_lack_of_card(self):
        view, _send = self.create_charge()
        charge = self._age(60)
        charge.sudo().write({'state': 'cancelled', 'timed_out': True})
        with patch(SEND, return_value=self.loose()):
            self.provider._xpago_handle_notice({'object': {'kind': 'payment', 'id': 'pay-loose'}})
        self.assertEqual((charge.state, charge.timed_out), ('confirmed', False))
        with patch(SEND) as send:
            again = self.method.xpago_create_charge({'amount': 150.5, 'order_uuid': 'abcdef12-3456'})
        send.assert_not_called()
        self.assertEqual(again['id'], view['id'], '«Retry» closes the sale with it')

    def test_a_loose_payment_of_another_terminal_amount_or_tied_elsewhere_pays_nothing(self):
        self.create_charge()
        charge = self._age(60)
        for payment in (self.loose(serial='OTRA-0002'), self.loose(amount=99.0),
                        self.loose(terminal_charge_id='pi-9'), self.loose(status='refunded'), self.loose(card_present=False)):
            with patch(SEND, return_value=payment):
                self.provider._xpago_handle_notice({'object': {'kind': 'payment', 'id': 'pay-loose'}})
            self.assertEqual(charge.state, 'pending')

    def test_a_loose_payment_belongs_to_the_charge_sent_last_to_the_terminal(self):
        self.create_charge()
        first = self._age(120)
        self.create_charge()
        second = self._age(60)
        with patch(SEND, return_value=self.loose()):
            self.provider._xpago_handle_notice({'object': {'kind': 'payment', 'id': 'pay-loose'}})
        self.assertEqual((first.state, second.state), ('pending', 'confirmed'))

    def test_timeout_finds_the_loose_payment_instead_of_cancelling(self):
        view, _send = self.create_charge()
        charge = self._age(60)
        with patch(SEND, side_effect=[self.intent(), {'data': [self.loose()]}]) as send:
            result = self.method.xpago_timeout_charge(view['id'])
        self.assertEqual(send.call_args.args, ('GET', '/v1/payments'))
        self.assertEqual(send.call_args.kwargs['params']['status'], ['paid'])
        self.assertEqual((result['state'], result['timed_out'], charge.payment_id), ('confirmed', False, 'pay-loose'))

    def test_instant_notice_settles_the_terminal_charge(self):
        view, _send = self.create_charge()
        with patch(SEND, return_value=self.approved()) as send:
            self.provider._xpago_handle_notice({'object': {'kind': 'terminal_charge', 'id': 'pi-1', 'payment_id': 'pay-1'}})
        self.assertEqual(send.call_args.args, ('GET', '/v1/terminal-charges/pi-1'))
        charge = self.env['pos.xpago.charge'].browse(view['id'])
        self.assertEqual((charge.state, charge.card_no), ('confirmed', '4242'))
        # A refund made on the terminal app: the notice names the payment, Odoo reads the charge again.
        with patch(SEND, return_value={**self.approved(), 'status': 'refunded'}):
            self.provider._xpago_handle_notice({'object': {'kind': 'payment', 'id': 'pay-1'}})
        self.assertEqual(charge.state, 'refunded')
