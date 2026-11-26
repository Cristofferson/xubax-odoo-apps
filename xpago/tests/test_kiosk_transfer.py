from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.xpago.controllers.self_order_main import PosSelfOrderXpagoController
from odoo.addons.xpago.tests import test_pos_payment_rules
from odoo.addons.xpago.tests.test_pos_transfer import ANA, clabe, paid

SEND = test_pos_payment_rules.SEND
# Odoo 18 has no pos.order._send_payment_result: the kiosk hears the payment through XPago's own notice.
RESULT = 'odoo.addons.xpago.models.self_order_pos_xpago_charge.PosXpagoCharge._xpago_notify_kiosk'


def api(routes):
    """A fake XPago answering by endpoint; records every call."""
    calls = []

    def send(self, method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        for (m, path), answer in routes.items():
            if m == method and endpoint == path:
                return answer() if callable(answer) else answer
        raise AssertionError(f"unexpected call {method} {endpoint}")
    return send, calls


@tagged('post_install', '-at_install')
class TestKioskTransfer(test_pos_payment_rules.PosXpagoRulesCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.spei = cls.env['pos.payment.method'].create({
            'name': 'Transferencia XPago',
            'journal_id': cls.company_data['default_journal_bank'].id,
            'payment_method_type': 'terminal',
            'use_payment_terminal': 'xpago_spei',
            'xpago_provider_id': cls.provider.id,
        })
        cls.config.payment_method_ids = [(4, cls.spei.id)]

    def kiosk_order(self, product):
        if not self.config.current_session_id:
            self.config.open_ui()
        return self.env['pos.order'].create({
            'session_id': self.config.current_session_id.id, 'amount_tax': 0, 'amount_total': product.list_price,
            'amount_paid': 0, 'amount_return': 0,
            'lines': [(0, 0, {'product_id': product.id, 'qty': 1, 'price_unit': product.list_price,
                              'price_subtotal': product.list_price, 'price_subtotal_incl': product.list_price})],
        })

    def start(self, order, routes=None):
        routes = routes or {('POST', '/v1/checkouts'): {'id': 'chk-1', 'bank_transfer': clabe(amount=200.0)}}
        send, calls = api(routes)
        with patch(SEND, send), patch(RESULT) as result:
            transfer = self.spei._xpago_kiosk_transfer(order, ANA)
        return transfer, calls, result

    def refresh(self, transfer, remote, checkout='paid'):
        send, calls = api({('GET', '/v1/checkouts/chk-1/bank-transfer'): remote,
                           ('GET', '/v1/checkouts/chk-1'): {'id': 'chk-1', 'status': checkout,
                                                            'payment': {'id': 'pay-9', 'operation_code': 'OP-77'}}})
        with patch(SEND, send), patch(RESULT) as result:
            transfer._xpago_refresh()
        return result

    def test_the_kiosk_offers_the_transfer(self):
        # A kiosk takes no cash.
        self.config.write({'payment_method_ids': [(6, 0, (self.method | self.spei).ids)], 'self_ordering_mode': 'kiosk'})
        data = {'pos.config': [{'id': self.config.id, 'self_ordering_mode': 'kiosk',
                                         'payment_method_ids': self.config.payment_method_ids.ids}]}
        domain = self.env['pos.payment.method']._load_pos_self_data_domain(data)
        methods = self.env['pos.payment.method'].search(domain)
        self.assertIn(self.spei, methods)
        self.assertIn(self.method, methods)
        # The kiosk knows how long it waits for the money.
        self.assertIn('xpago_kiosk_transfer_timeout', self.env['pos.config']._load_pos_self_data_fields(self.config.id))

    def test_the_clabe_is_made_for_the_order_and_who_pays(self):
        order = self.kiosk_order(self.cleaner)
        transfer, calls, _result = self.start(order)
        self.assertEqual(transfer.pos_order_id, order)
        self.assertEqual(transfer.state, 'awaiting')
        self.assertEqual(transfer.clabe, '738180000000012345')
        method, endpoint, kwargs = calls[0]
        self.assertEqual((method, endpoint), ('POST', '/v1/checkouts'))
        self.assertEqual(kwargs['json']['methods'], ['bank_transfer'])
        self.assertEqual(kwargs['json']['amount'], 200.0)
        self.assertEqual(kwargs['json']['customer']['email'], 'ana@example.com')
        self.assertEqual(kwargs['json']['deposit_account_id'], 'a-main', 'the payment rules of the kiosk decide the account')

    def test_the_transfer_pays_the_kiosk_order(self):
        order = self.kiosk_order(self.cleaner)
        transfer, _calls, _result = self.start(order)
        result = self.refresh(transfer, paid(amount=200.0))
        self.assertEqual(transfer.state, 'paid')
        self.assertEqual(order.state, 'paid')
        payment = order.payment_ids
        self.assertEqual(payment.payment_method_id, self.spei)
        self.assertEqual(payment.amount, 200.0)
        self.assertEqual(payment.transaction_id, 'pay-9')
        self.assertEqual(payment.card_type, 'SPEI')
        result.assert_called_once_with(order, 'Success')
        self.assertFalse(transfer.without_sale)
        # Read again: nothing is paid twice.
        transfer._xpago_complete_kiosk_orders()
        self.assertEqual(len(order.payment_ids), 1)

    def test_asking_again_shows_the_same_clabe(self):
        order = self.kiosk_order(self.cleaner)
        first, _calls, _result = self.start(order)
        again, calls, _result = self.start(order, {('GET', '/v1/checkouts/chk-1'): {'id': 'chk-1', 'status': 'open'},
                                                  ('GET', '/v1/checkouts/chk-1/bank-transfer'): clabe(amount=200.0)})
        self.assertEqual(again, first)
        self.assertNotIn('POST', [c[0] for c in calls], 'no second CLABE for the same order')

    def test_money_that_already_arrived_pays_the_order_on_retry(self):
        order = self.kiosk_order(self.cleaner)
        first, _calls, _result = self.start(order)
        again, _calls, result = self.start(order, {
            ('GET', '/v1/checkouts/chk-1/bank-transfer'): paid(amount=200.0),
            ('GET', '/v1/checkouts/chk-1'): {'id': 'chk-1', 'status': 'paid', 'payment': {'id': 'pay-9'}}})
        self.assertEqual(again, first)
        self.assertEqual(order.state, 'paid')
        result.assert_called_once_with(order, 'Success')

    def test_a_cancelled_clabe_tells_the_kiosk(self):
        order = self.kiosk_order(self.cleaner)
        transfer, _calls, _result = self.start(order)
        result = self.refresh(transfer, clabe('canceled', amount=200.0), checkout='canceled')
        self.assertEqual(transfer.state, 'cancelled')
        self.assertEqual(order.state, 'draft')
        result.assert_called_once_with(order, 'fail')

    def test_the_card_route_refuses_a_transfer(self):
        order = self.kiosk_order(self.cleaner)
        with self.assertRaises(UserError):
            self.spei._payment_request_from_kiosk(order)

    def age(self, transfer, seconds):
        self.env.cr.execute("UPDATE pos_xpago_transfer SET create_date = %s WHERE id = %s",
                            [fields.Datetime.now() - timedelta(seconds=seconds), transfer.id])
        transfer.invalidate_recordset(['create_date'])

    def test_an_abandoned_kiosk_clabe_is_cancelled(self):
        order = self.kiosk_order(self.cleaner)
        transfer, _calls, _result = self.start(order)
        self.assertEqual(self.config.xpago_kiosk_transfer_timeout, 600)
        self.age(transfer, 30)
        send, calls = api({})
        with patch(SEND, send):
            self.env['pos.xpago.transfer']._xpago_cancel_abandoned_kiosk_transfers()
        self.assertFalse(calls, 'a recent CLABE is left waiting')
        self.age(transfer, 700)
        send, calls = api({('POST', '/v1/checkouts/chk-1/cancel'): {'id': 'chk-1', 'status': 'canceled'}})
        with patch(SEND, send), patch(RESULT) as result:
            self.env['pos.xpago.transfer']._xpago_cancel_abandoned_kiosk_transfers()
        self.assertEqual(transfer.state, 'cancelled')
        result.assert_called_once_with(order, 'fail')

    def test_the_kiosk_sees_no_customer_data(self):
        order = self.kiosk_order(self.cleaner)
        transfer, _calls, _result = self.start(order)
        view = PosSelfOrderXpagoController._xpago_kiosk_transfer_view(transfer)
        self.assertEqual(view['clabe'], '738180000000012345')
        self.assertNotIn('customer_phone', view)
        self.assertNotIn('payment', view)
