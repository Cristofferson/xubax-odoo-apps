from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon

SEND = 'odoo.addons.xpago.models.payment_provider.PaymentProvider._send_api_request'


@tagged('post_install', '-at_install')
class TestKioskXpago(TestPoSCommon):
    """The kiosk sends the order's amount to the terminal; the approved card pays the order by itself."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env['payment.provider'].sudo().search([('code', '=', 'xpago')], limit=1).copy(
            {'company_id': cls.env.company.id})
        cls.provider.write({'xpago_api_key': 'xpk_test_key', 'is_live': False})
        cls.method = cls.env['pos.payment.method'].create({
            'name': 'XPago kiosk',
            'type': 'bank',
            'journal_id': cls.company_data['default_journal_bank'].id,
            'payment_method_type': 'terminal',
            'payment_provider': 'xpago',
            'xpago_provider_id': cls.provider.id,
            'xpago_terminal_serial': 'N950-0002',
        })

    def intent(self, status='pending', **extra):
        return {'id': 'pi-k1', 'status': status, 'expires_at': '2099-01-01T00:10:00.000Z',
                'terminal_app_url': 'xpago-terminal://charge/pi-k1', **extra}

    def approved(self):
        return self.intent('paid', payment={
            'id': 'pay-k1', 'operation_code': '654321', 'authorization_code': 'K1',
            'card': {'funding': 'DEBIT', 'brand': 'VISA', 'last4': '4242'},
        })

    def setUp(self):
        super().setUp()
        self.config = self.basic_config
        self.config.write({'self_ordering_mode': 'kiosk', 'payment_method_ids': [(6, 0, self.method.ids)]})
        self.product = self.create_product('Kiosk product', self.categ_basic, 150.5, 50)
        self.open_new_session()
        data = self.create_ui_order_data([(self.product, 1)], payments=[])
        data['state'] = 'draft'
        result = self.env['pos.order'].sync_from_ui([data])
        self.order = self.env['pos.order'].browse(result['pos.order'][0]['id'])

    def test_kiosk_charge_pays_the_order(self):
        with patch(SEND, return_value=self.intent()) as send:
            status = self.method._payment_request_from_kiosk(self.order)
        self.assertEqual(send.call_args.args, ('POST', '/v1/terminal-charges'))
        self.assertEqual(send.call_args.kwargs['json']['amount'], self.order.amount_total)
        # The kiosk routes read the charge back as superuser, like here.
        charge = self.env['pos.xpago.charge'].sudo().browse(status['xpago_charge_id'])
        self.assertEqual((charge.state, charge.pos_order_id), ('pending', self.order))
        with patch(SEND, return_value=self.approved()), \
                patch.object(type(self.config), '_notify') as notify:
            charge._xpago_refresh()
        self.assertEqual(self.order.state, 'paid')
        self.assertEqual(self.order.payment_ids.card_no, '4242')
        self.assertEqual(notify.call_args.args[0], 'PAYMENT_STATUS')
        self.assertEqual(notify.call_args.args[1]['payment_result'], 'Success')

    def test_cancelled_kiosk_charge_tells_the_kiosk(self):
        with patch(SEND, return_value=self.intent()):
            status = self.method._payment_request_from_kiosk(self.order)
        # The kiosk routes read the charge back as superuser, like here.
        charge = self.env['pos.xpago.charge'].sudo().browse(status['xpago_charge_id'])
        with patch(SEND, return_value=self.intent('canceled')), \
                patch.object(type(self.config), '_notify') as notify:
            charge._xpago_cancel()
        self.assertEqual((charge.state, self.order.state), ('cancelled', 'draft'))
        self.assertEqual(notify.call_args.args[1]['payment_result'], 'fail')

    def test_kiosk_loads_the_xpago_terminal(self):
        domain = self.env['pos.payment.method']._load_pos_self_data_domain({'pos.config': self.config})
        self.assertIn(self.method, self.env['pos.payment.method'].search(domain))

    def test_kiosk_loads_the_card_voucher_settings(self):
        fields = self.env['pos.config']._load_pos_self_data_fields(self.config.id)
        self.assertIn('xpago_voucher_on_receipt', fields)
        self.assertIn('xpago_voucher_credit_text', fields)
