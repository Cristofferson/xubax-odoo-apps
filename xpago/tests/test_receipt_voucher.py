from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged('post_install', '-at_install')
class TestPosXpagoVoucher(TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env['payment.provider'].search([('code', '=', 'xpago')], limit=1)
        cls.provider.write({'xpago_api_key': 'xpk_test_key', 'is_live': False, 'company_id': cls.env.company.id})
        cls.method = cls.env['pos.payment.method'].create({
            'name': 'Tarjeta XPago',
            'type': 'bank',
            'journal_id': cls.company_data['default_journal_bank'].id,
            'payment_method_type': 'terminal',
            'payment_provider': 'xpago',
            'xpago_provider_id': cls.provider.id,
            'xpago_terminal_serial': 'N950-0001',
        })
        cls.config = cls.basic_config
        cls.config.payment_method_ids = [(4, cls.method.id)]
        cls.product = cls.env['product.product'].create({'name': 'Anillo', 'list_price': 150.5, 'available_in_pos': True,
                                                         'taxes_id': [(6, 0, [])]})

    def paid_order(self, card_type='CREDIT'):
        self.open_new_session()
        data = self.create_ui_order_data([(self.product, 1)], payments=[(self.method, 150.5)])
        order = self.env['pos.order'].browse(self.env['pos.order'].sync_from_ui([data])['pos.order'][0]['id'])
        order.payment_ids.write({
            'card_brand': 'VISA', 'card_no': '4242', 'card_type': card_type, 'transaction_id': 'pay-1',
            'payment_ref_no': '123456', 'payment_method_authcode': 'A1B2C3', 'payment_method_issuer_bank': 'BBVA',
            'payment_method_payment_mode': 'CHIP',
        })
        return order

    def test_voucher_is_on_by_default(self):
        config = self.env['pos.config'].create({'name': 'Caja nueva'})
        self.assertTrue(config.xpago_voucher_on_receipt)
        self.assertTrue(config.xpago_voucher_signature)
        self.assertIn('pagaré', config.xpago_voucher_credit_text)
        self.assertTrue(config.xpago_voucher_debit_text)

    def test_settings_write_the_point_of_sale(self):
        settings = self.env['res.config.settings'].create({'pos_config_id': self.config.id})
        settings.write({'pos_xpago_voucher_on_receipt': False, 'pos_xpago_voucher_merchant': '7654321'})
        settings.execute()
        self.assertFalse(self.config.xpago_voucher_on_receipt)
        self.assertEqual(self.config.xpago_voucher_merchant, '7654321')

    def test_card_voucher_in_the_receipt(self):
        self.config.xpago_voucher_merchant = '7654321'
        order = self.paid_order()
        payment = order.order_receipt_generate_data()['payments'][0]
        self.assertTrue(payment['xpago_voucher'])
        self.assertTrue(payment['xpago_credit'])
        html = str(order.order_receipt_generate_html())
        for text in ('CARD SALE', '**** 4242', 'A1B2C3', 'Operation: 123456', 'BBVA', 'CHIP', '7654321', 'pagaré'):
            self.assertIn(text, html)
        # Chip and contactless are never signed; a swiped card is.
        self.assertNotIn("Customer's signature", html)
        order.payment_ids.payment_method_payment_mode = 'SWIPE'
        self.assertIn("Customer's signature", str(order.order_receipt_generate_html()))
        # The processor's internal id stays stored, but out of the customer's ticket.
        self.assertEqual(order.payment_ids.transaction_id, 'pay-1')
        self.assertNotIn('pay-1', html)
        self.assertNotIn('Reference:', html)

    def test_debit_legend(self):
        order = self.paid_order('DEBIT')
        html = str(order.order_receipt_generate_html())
        self.assertIn('Autorizo que se cargue a mi cuenta', html)
        self.assertNotIn('pagaré', html)

    def test_no_voucher_when_disabled(self):
        self.config.xpago_voucher_on_receipt = False
        order = self.paid_order()
        self.assertFalse(order.order_receipt_generate_data()['payments'][0]['xpago_voucher'])
        self.assertNotIn('CARD SALE', str(order.order_receipt_generate_html()))

    def test_no_voucher_when_odoo_prints_on_the_terminal(self):
        """The terminal prints its certified voucher right under Odoo's receipt: Odoo leaves its own out."""
        self.config.xpago_print_on_terminal = True
        order = self.paid_order()
        self.assertFalse(order.order_receipt_generate_data()['payments'][0]['xpago_voucher'])
        self.assertNotIn('CARD SALE', str(order.order_receipt_generate_html()))
