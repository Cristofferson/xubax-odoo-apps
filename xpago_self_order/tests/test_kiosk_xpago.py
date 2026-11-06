from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon

SEND = 'odoo.addons.xpago.models.payment_provider.PaymentProvider._xpago_make_request'


@tagged('post_install', '-at_install')
class TestKioskXpago(TestPoSCommon):
    """The kiosk sends the order's amount to the terminal; the approved card pays the order by itself."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env['payment.provider'].sudo().search([('code', '=', 'xpago')], limit=1).copy(
            {'company_id': cls.env.company.id})
        cls.provider.write({'xpago_api_key': 'xpk_test_key', 'state': 'test'})
        cls.method = cls.env['pos.payment.method'].create({
            'name': 'XPago kiosk',
            'journal_id': cls.company_data['default_journal_bank'].id,
            'use_payment_terminal': 'xpago',
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
        result = self.env['pos.order'].create_from_ui([data], draft=True)
        self.order = self.env['pos.order'].browse(result[0]['id'])

    def test_kiosk_charge_pays_the_order(self):
        with patch(SEND, return_value=self.intent()) as send:
            status = self.method._payment_request_from_kiosk(self.order)
        self.assertEqual(send.call_args.args, ('POST', '/v1/terminal-charges'))
        self.assertEqual(send.call_args.kwargs['json']['amount'], self.order.amount_total)
        # The kiosk routes read the charge back as superuser, like here.
        charge = self.env['pos.xpago.charge'].sudo().browse(status['xpago_charge_id'])
        self.assertEqual((charge.state, charge.pos_order_id), ('pending', self.order))
        with patch(SEND, return_value=self.approved()), \
                patch.object(type(self.env['bus.bus']), '_sendone') as notify:
            charge._xpago_refresh()
        self.assertEqual(self.order.state, 'paid')
        self.assertEqual(self.order.payment_ids.transaction_id, 'pay-k1')
        self.assertIn('•••• 4242', self.order.payment_ids.ticket)
        [(channel, kind, payload)] = [c.args for c in notify.call_args_list if c.args[1] == 'PAYMENT_STATUS']
        self.assertEqual((channel, kind), (f'pos_config-{self.config.access_token}', 'PAYMENT_STATUS'))
        self.assertEqual(payload['payment_result'], 'Success')
        self.assertEqual(payload['order']['id'], self.order.id)
        # The ticket the kiosk prints carries the card voucher (debit card: the debit legend).
        [voucher] = [line['xpago_voucher'] for line in payload['order']['payment_lines']]
        self.assertEqual((voucher['brand'], voucher['card_no'], voucher['authorization'], voucher['operation'],
                          voucher['funding']), ('VISA', '4242', 'K1', '654321', 'Debit'))
        self.assertNotIn('reference', voucher)
        self.assertEqual(voucher['legend'], self.config.xpago_voucher_debit_text)
        self.config.xpago_voucher_on_receipt = False
        self.assertFalse(self.order._export_for_self_order()['payment_lines'][0]['xpago_voucher'])

    def test_cancelled_kiosk_charge_tells_the_kiosk(self):
        with patch(SEND, return_value=self.intent()):
            status = self.method._payment_request_from_kiosk(self.order)
        # The kiosk routes read the charge back as superuser, like here.
        charge = self.env['pos.xpago.charge'].sudo().browse(status['xpago_charge_id'])
        with patch(SEND, return_value=self.intent('canceled')), \
                patch.object(type(self.env['bus.bus']), '_sendone') as notify:
            charge._xpago_cancel()
        self.assertEqual((charge.state, self.order.state), ('cancelled', 'draft'))
        [payload] = [c.args[2] for c in notify.call_args_list if c.args[1] == 'PAYMENT_STATUS']
        self.assertEqual(payload['payment_result'], 'fail')

    def test_kiosk_offers_the_xpago_terminal(self):
        self.assertIn(self.method, self.config._get_allowed_payment_methods())
        data = self.config._get_self_ordering_data()
        self.assertIn(self.method.id, [m['id'] for m in data['pos_payment_methods']])

    def test_kiosk_route_starts_the_charge(self):
        # What /kiosk/payment does with the order the kiosk sends.
        with patch(SEND, return_value=self.intent()):
            status = self.method.sudo()._payment_request_from_kiosk(self.order)
        self.assertTrue(status['xpago_charge_id'])
        charge = self.env['pos.xpago.charge'].sudo().browse(status['xpago_charge_id'])
        self.assertEqual(charge.config_id, self.config)
        self.assertEqual(charge.order_uuid, self.order.access_token or self.order.pos_reference)

    def test_kiosk_assets_carry_the_voucher(self):
        # The kiosk prints its ticket with the receipt template of the point of sale, and its voucher.
        bundle = self.env['ir.qweb']._get_asset_bundle('pos_self_order.assets', css=False)
        self.assertIn('/xpago_pos/static/src/app/order_receipt_voucher.xml', [f['url'] for f in bundle.files])
        templates = bundle.xml()  # raises when the voucher does not apply to the receipt
        self.assertIn('xpago-voucher', templates)
        self.assertIn('line.ticket and !line.xpago_voucher', templates)
