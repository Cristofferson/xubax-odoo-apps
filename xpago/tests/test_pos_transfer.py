from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.addons.xpago.tests.common import XpagoCommon

SEND = 'odoo.addons.xpago.models.payment_provider.PaymentProvider._xpago_make_request'
ANA = {'name': 'Ana Ruiz López', 'email': 'ana@example.com', 'phone': '55 1234 5678'}


def clabe(status='awaiting', **extra):
    return {'id': 'bt1', 'status': status, 'rail': 'spei', 'clabe': '738180000000012345', 'clabe_last4': '2345',
            'bank': 'FINTOC', 'beneficiary': 'Sharepay SA de CV', 'concept': 'Compra Anello 5B1E2D',
            'amount': 1200.0, 'amount_received': 0, 'amount_due': 1200.0, 'currency': 'MXN',
            'expires_at': '2099-01-01T01:00:00.000Z', 'url': 'https://pay.example.com/otp/chk-1?spei=bt1', **extra}


def paid(**extra):
    return clabe('paid', clabe=None, amount_received=1200.0, amount_due=0, paid_at='2099-01-01T00:20:00.000Z',
                 payment_id='pay-9', **extra)


@tagged('post_install', '-at_install')
class TestPosXpagoTransfer(TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A provider of the test company, like the payment tests prepare theirs.
        cls.provider = cls.env['payment.provider'].sudo().search([('code', '=', 'xpago')], limit=1).copy(
            {'company_id': cls.env.company.id})
        cls.provider.write({'xpago_api_key': 'xpk_test_key', 'state': 'test'})
        cls.method = cls.env['pos.payment.method'].create({
            'name': 'Transferencia XPago',
            'journal_id': cls.company_data['default_journal_bank'].id,
            'payment_method_type': 'terminal',
            'use_payment_terminal': 'xpago_spei',
            'xpago_provider_id': cls.provider.id,
        })

    def create_transfer(self, answer=None, customer=ANA, amount=1200.0):
        created = answer if answer is not None else {'id': 'chk-1', 'checkout_url': 'https://pay.example.com/otp/chk-1',
                                                     'bank_transfer': clabe()}
        with patch(SEND, return_value=created) as send:
            view = self.method.xpago_transfer_create({'amount': amount, 'order_uuid': 'abcdef12-3456', 'customer': customer})
        return view, send

    def transfer(self, view):
        return self.env['pos.xpago.transfer'].sudo().browse(view['id'])

    def test_the_clabe_is_made_with_the_sale_and_who_pays(self):
        view, send = self.create_transfer()
        method, endpoint = send.call_args.args
        body = send.call_args.kwargs['json']
        self.assertEqual((method, endpoint), ('POST', '/v1/checkouts'))
        self.assertEqual(body['methods'], ['bank_transfer'], 'a register transfer offers only the transfer')
        self.assertEqual(body['bank_transfer_at'], 'create', 'the CLABE comes back right away for the register')
        self.assertEqual(body['customer'], {'first_name': 'Ana', 'last_name': 'Ruiz López', 'email': 'ana@example.com',
                                            'phone': '+525512345678'})
        self.assertEqual(body['amount'], 1200.0)
        self.assertEqual(send.call_args.kwargs['idempotency_key'], body['reference'])
        self.assertEqual(view['state'], 'awaiting')
        self.assertEqual((view['clabe'], view['bank'], view['beneficiary']), ('738180000000012345', 'FINTOC', 'Sharepay SA de CV'))
        self.assertEqual(view['business'], self.method.company_id.name, 'the business is shown beside the beneficiary')
        self.assertTrue(view['expires_at'])
        self.assertEqual(self.transfer(view).xpago_id, 'chk-1')

    def test_who_pays_is_required(self):
        with self.assertRaises(UserError):
            self.create_transfer(customer={'name': 'Ana', 'email': '', 'phone': ''})

    def test_a_missing_clabe_is_asked_for_again(self):
        """The bank did not answer in time when the page was made: Odoo asks for its CLABE."""
        with patch(SEND, side_effect=[{'id': 'chk-1', 'checkout_url': 'https://x'}, clabe()]) as send:
            view = self.method.xpago_transfer_create({'amount': 1200.0, 'order_uuid': 'abcdef12', 'customer': ANA})
        self.assertEqual(send.call_args_list[1].args, ('POST', '/v1/checkouts/chk-1/bank-transfer'))
        self.assertEqual(view['clabe'], '738180000000012345')

    def test_refusal_tells_the_cashier(self):
        with patch(SEND, side_effect=ValidationError('SPEI is not enabled')), self.assertRaises(UserError):
            self.method.xpago_transfer_create({'amount': 1200.0, 'order_uuid': 'abcdef12', 'customer': ANA})

    def test_negative_amount_is_refused(self):
        with self.assertRaises(UserError):
            self.create_transfer(amount=-5)

    def test_partial_then_paid(self):
        view, _send = self.create_transfer()
        with patch(SEND, return_value=clabe(amount_received=200.0, amount_due=1000.0)):
            view = self.method.xpago_transfer_status(view['id'])
        self.assertEqual((view['state'], view['amount_received'], view['amount_due']), ('awaiting', 200.0, 1000.0))
        checkout = {'id': 'chk-1', 'status': 'paid', 'payment': {'id': 'pay-9', 'operation_code': '777001', 'method': 'bank_transfer'}}
        with patch(SEND, side_effect=[paid(), checkout]):
            view = self.method.xpago_transfer_status(view['id'])
        self.assertEqual(view['state'], 'paid')
        self.assertFalse(view['clabe'], 'the whole CLABE is only kept while it takes money')
        self.assertEqual(view['payment'], {
            'transaction_id': 'pay-9', 'payment_ref_no': '777001', 'card_no': '2345', 'card_type': 'SPEI',
            'payment_method_payment_mode': 'SPEI', 'cardholder_name': 'Ana Ruiz López'})

    def test_expired_clabe_is_replaced_for_the_same_sale(self):
        view, _send = self.create_transfer()
        with patch(SEND, return_value=clabe('expired', clabe=None)):
            view = self.method.xpago_transfer_status(view['id'])
        self.assertEqual((view['state'], view['clabe']), ('expired', ''))
        with patch(SEND, return_value=clabe(id='bt2', clabe='738180000000067890', clabe_last4='7890')) as send:
            view = self.method.xpago_transfer_renew(view['id'])
        self.assertEqual(send.call_args.args, ('POST', '/v1/checkouts/chk-1/bank-transfer'))
        self.assertEqual((view['state'], view['clabe']), ('awaiting', '738180000000067890'))
        with self.assertRaises(UserError):
            self.method.xpago_transfer_renew(view['id'])

    def test_cancel(self):
        view, _send = self.create_transfer()
        with patch(SEND, return_value={'id': 'chk-1', 'status': 'canceled'}) as send:
            view = self.method.xpago_transfer_cancel(view['id'])
        self.assertEqual(send.call_args.args, ('POST', '/v1/checkouts/chk-1/cancel'))
        self.assertEqual((view['state'], view['clabe']), ('cancelled', ''))

    def test_money_arrived_before_the_cancel_stays_paid(self):
        view, _send = self.create_transfer()
        checkout = {'id': 'chk-1', 'status': 'paid', 'payment': {'id': 'pay-9', 'operation_code': '777001'}}
        with patch(SEND, side_effect=[ValidationError('checkout_closed'), paid(), checkout]):
            view = self.method.xpago_transfer_cancel(view['id'])
        self.assertEqual(view['state'], 'paid')

    def test_paid_transfer_notifies_once(self):
        self.provider.xpago_notify_user_ids = self.env.user
        view, _send = self.create_transfer()
        transfer = self.transfer(view)
        checkout = {'id': 'chk-1', 'status': 'paid', 'payment': {'id': 'pay-9', 'operation_code': '777001'}}
        with patch(SEND, side_effect=[paid(), checkout]), \
                patch('odoo.addons.xpago.models.payment_provider.PaymentProvider._xpago_notify') as notify:
            transfer._xpago_refresh()
            transfer._xpago_refresh()
        self.assertEqual(notify.call_count, 1)

    def test_force_done_only_with_the_money(self):
        view, _send = self.create_transfer()
        with patch(SEND, return_value=clabe()):
            answer = self.method.xpago_transfer_force_check({'order_uuid': 'abcdef12-3456', 'amount': 1200.0})
        self.assertEqual(answer['state'], 'awaiting')
        checkout = {'id': 'chk-1', 'status': 'paid', 'payment': {'id': 'pay-9', 'operation_code': '777001'}}
        with patch(SEND, side_effect=[paid(), checkout]):
            answer = self.method.xpago_transfer_force_check({'order_uuid': 'abcdef12-3456', 'amount': 1200.0})
        self.assertEqual((answer['state'], answer['payment']['transaction_id']), ('paid', 'pay-9'))
        answer = self.method.xpago_transfer_force_check({'order_uuid': 'abcdef12-3456', 'amount': 99.0})
        self.assertEqual(answer['state'], 'unmatched')
        self.assertEqual(self.method.xpago_transfer_force_check({'order_uuid': 'other'})['state'], 'none')

    def test_paid_transfer_without_order_is_found(self):
        view, _send = self.create_transfer()
        transfer = self.transfer(view)
        transfer.write({'state': 'paid', 'payment_id': 'pay-9'})
        self.env.cr.execute("UPDATE pos_xpago_transfer SET create_date = now() - interval '1 hour' WHERE id = %s", [transfer.id])
        transfer.invalidate_recordset()
        self.assertIn(transfer, self.env['pos.xpago.transfer'].search([('without_sale', '=', True)]))

    def test_a_terminal_method_does_not_take_transfers(self):
        card = self.env['pos.payment.method'].create({
            'name': 'Tarjeta', 'journal_id': self.company_data['default_journal_bank'].id,
            'payment_method_type': 'terminal', 'use_payment_terminal': 'xpago', 'xpago_provider_id': self.provider.id,
            'xpago_terminal_serial': 'N950-1'})
        with self.assertRaises(UserError):
            card.xpago_transfer_create({'amount': 10.0, 'customer': ANA})

    def test_the_account_is_required(self):
        with self.assertRaises(UserError):
            self.env['pos.payment.method'].create({
                'name': 'Transferencia', 'journal_id': self.company_data['default_journal_bank'].id,
                'payment_method_type': 'terminal', 'use_payment_terminal': 'xpago_spei', 'xpago_provider_id': False})

    def test_cron_reads_back_open_transfers(self):
        view, _send = self.create_transfer()
        checkout = {'id': 'chk-1', 'status': 'paid', 'payment': {'id': 'pay-9', 'operation_code': '777001'}}
        with patch(SEND, side_effect=[paid(), checkout]):
            self.env['pos.xpago.transfer']._xpago_cron_refresh()
        self.assertEqual(self.transfer(view).state, 'paid')


@tagged('post_install', '-at_install')
class TestOnlineTransfer(XpagoCommon):

    def test_online_checkout_offers_the_transfer_when_asked(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id)
        self.assertNotIn('methods', tx._xpago_prepare_checkout_payload(), 'by default XPago decides')
        self.provider.xpago_offer_bank_transfer = True
        payload = tx._xpago_prepare_checkout_payload()
        self.assertEqual(payload['methods'], ['card', 'bank_transfer'])
        self.assertEqual(payload['default_method'], 'card')
        self.assertNotIn('bank_transfer_at', payload, 'the CLABE is made when the customer picks it')

    def test_waiting_for_the_transfer_says_so(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, provider_reference=self.checkout_id)
        tx._handle_notification_data('xpago', self.payment_data('pending', bank_transfer={'status': 'awaiting', 'clabe_last4': '2345'}))
        self.assertEqual(tx.state, 'pending')
        self.assertIn('2345', tx.state_message)
        tx._handle_notification_data('xpago', self.payment_data('paid', bank_transfer={'status': 'paid', 'clabe_last4': '2345'}))
        self.assertEqual(tx.state, 'done')
