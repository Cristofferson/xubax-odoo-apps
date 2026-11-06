from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon

SEND = 'odoo.addons.xpago.models.payment_provider.PaymentProvider._send_api_request'


class PosXpagoRulesCommon(TestPoSCommon):
    """A terminal and the rules of a jewelry shop: 12 months on jewelry over $5,000, the marketplace pieces to the
    escrow account with up to 6 months, and anything under $1,000 single payment to the main account."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env['payment.provider'].search([('code', '=', 'xpago')], limit=1)
        cls.provider.write({'xpago_api_key': 'xpk_test_key', 'state': 'test', 'company_id': cls.env.company.id})
        cls.method = cls.env['pos.payment.method'].create({
            'name': 'Tarjeta XPago',
            'journal_id': cls.company_data['default_journal_bank'].id,
            'payment_method_type': 'terminal',
            'use_payment_terminal': 'xpago',
            'xpago_provider_id': cls.provider.id,
            'xpago_terminal_serial': 'N950-0001',
        })
        cls.config = cls.basic_config
        Account = cls.env['payment.xpago.bank.account']
        cls.acc_main = Account.create({'provider_id': cls.provider.id, 'xpago_id': 'a-main', 'name': 'Operación'})
        cls.acc_escrow = Account.create({'provider_id': cls.provider.id, 'xpago_id': 'a-escrow', 'name': 'Escrow'})
        cls.acc_terminal = Account.create({'provider_id': cls.provider.id, 'xpago_id': 'a-terminal', 'name': 'Terminal'})
        cls.categ_jewel = cls.env['product.category'].create({'name': 'Joyería'})
        cls.categ_diamond = cls.env['product.category'].create({'name': 'Diamantes', 'parent_id': cls.categ_jewel.id})
        cls.tag_market = cls.env['product.tag'].create({'name': 'Marketplace'})
        Product = cls.env['product.product']
        cls.ring = Product.create({'name': 'Anillo', 'categ_id': cls.categ_diamond.id, 'list_price': 30000,
                                   'available_in_pos': True, 'taxes_id': [(6, 0, [])]})
        cls.used = Product.create({'name': 'Anillo seminuevo', 'list_price': 25000, 'available_in_pos': True,
                                   'product_tag_ids': [(6, 0, cls.tag_market.ids)], 'taxes_id': [(6, 0, [])]})
        cls.cleaner = Product.create({'name': 'Limpiador', 'list_price': 200, 'available_in_pos': True,
                                      'taxes_id': [(6, 0, [])]})
        Rule = cls.env['payment.xpago.rule']
        cls.r_jewel = Rule.create({'name': '12 MSI en joyería', 'sequence': 10, 'categ_ids': [(6, 0, cls.categ_jewel.ids)],
                                   'msi_mode': 'terms', 'terms': '3, 6, 12', 'price_min': 5000})
        cls.r_market = Rule.create({'name': 'Marketplace al escrow', 'sequence': 5, 'tag_ids': [(6, 0, cls.tag_market.ids)],
                                    'msi_mode': 'terms', 'terms': '3, 6', 'bank_account_id': cls.acc_escrow.id})
        cls.r_cheap = Rule.create({'name': 'Menos de $1,000 de contado', 'sequence': 20, 'price_max': 1000, 'msi_mode': 'none',
                                   'bank_account_id': cls.acc_main.id})

    def plan(self, products, split=False, channel='pos', config=None):
        lines = [{'product': p, 'unit_price': p.list_price, 'amount': p.list_price} for p in products]
        return self.env['payment.xpago.rule']._xpago_plan(
            self.env.company, channel, lines, sum(line['amount'] for line in lines), config=config, split=split)

    def intent(self):
        return {'id': 'pi-1', 'status': 'pending', 'expires_at': '2099-01-01T00:10:00.000Z',
                'terminal_app_url': 'xpago-terminal://charge/pi-1'}


@tagged('post_install', '-at_install')
class TestPosPaymentRules(PosXpagoRulesCommon):

    def test_channel_and_points_of_sale(self):
        part, = self.plan([self.used], channel='kiosk')
        self.assertEqual(part['account'], self.acc_escrow)
        self.r_market.use_kiosk = False
        part, = self.plan([self.used], channel='kiosk')
        self.assertFalse(part['account'])
        self.r_market.config_ids = self.config
        other = self.config.copy({'name': 'Otra caja'})
        part, = self.plan([self.used], config=other)
        self.assertFalse(part['account'])
        part, = self.plan([self.used], config=self.config)
        self.assertEqual(part['account'], self.acc_escrow)
        self.r_market.use_pos = False
        part, = self.plan([self.used], config=self.config)
        self.assertFalse(part['account'])
        part, = self.plan([self.used], channel='online')
        self.assertEqual(part['account'], self.acc_escrow, 'online does not look at the points of sale')

    def test_tip_is_not_a_product(self):
        """A tip of $50 fits the "up to $1,000" rule; it goes with the sale instead of becoming its own charge."""
        tip = self.env['product.product'].create({'name': 'Propina', 'list_price': 0, 'taxes_id': [(6, 0, [])]})
        self.config.write({'iface_tipproduct': True, 'tip_product_id': tip.id, 'xpago_split': True})
        session = self.env['pos.session'].create({'config_id': self.config.id, 'user_id': self.env.uid})
        plan = self.method.xpago_plan({'session_id': session.id, 'total': 30050, 'amount': 30050, 'lines': [
            {'product_id': self.ring.id, 'qty': 1, 'amount': 30000}, {'product_id': tip.id, 'qty': 1, 'amount': 50}]})
        part, = plan['parts']
        self.assertEqual((part['amount'], part['terms']), (30050, [1, 3, 6, 12]))

    def test_register_plan(self):
        session = self.env['pos.session'].create({'config_id': self.config.id, 'user_id': self.env.uid})
        data = {'session_id': session.id, 'total': 25200, 'amount': 25200,
                'lines': [{'product_id': self.used.id, 'qty': 1, 'amount': 25000},
                          {'product_id': self.cleaner.id, 'qty': 1, 'amount': 200}]}
        plan = self.method.xpago_plan(data)
        self.assertEqual(len(plan['parts']), 1, 'the point of sale does not split')
        self.assertEqual(plan['parts'][0]['account_id'], self.acc_escrow.id)
        self.assertEqual(plan['parts'][0]['terms'], [1])
        self.assertTrue(plan['show_account'])
        self.config.xpago_split = True
        plan = self.method.xpago_plan(data)
        parts = {p['account_name']: p for p in plan['parts']}
        self.assertEqual(sorted(p['amount'] for p in plan['parts']), [200, 25000])
        self.assertEqual(parts['Escrow']['terms'], [1, 3, 6])
        self.assertEqual(parts['Operación']['terms'], [1])
        self.assertIn('Marketplace al escrow', parts['Escrow']['rules'])
        plan = self.method.xpago_plan(dict(data, amount=10000))
        self.assertEqual(len(plan['parts']), 1, 'a partial payment is not split')
        self.assertEqual(plan['parts'][0]['amount'], 10000)
        self.assertEqual(plan['parts'][0]['account_id'], self.acc_escrow.id)

    def test_charge_goes_to_the_account_of_the_rules(self):
        self.method.xpago_bank_account_id = self.acc_terminal
        with patch(SEND, return_value=self.intent()) as send:
            view = self.method.xpago_create_charge({'amount': 25000, 'rule_account_id': self.acc_escrow.id})
        self.assertEqual(send.call_args.kwargs['json']['deposit_account_id'], 'a-escrow')
        self.assertEqual(self.env['pos.xpago.charge'].browse(view['id']).bank_account_id, self.acc_escrow)
        # Only an account a rule names comes from the plan.
        self.r_cheap.bank_account_id = False
        with patch(SEND, return_value=self.intent()) as send:
            self.method.xpago_create_charge({'amount': 200, 'rule_account_id': self.acc_main.id})
        self.assertEqual(send.call_args.kwargs['json']['deposit_account_id'], 'a-terminal')
        # The cashier's choice, when the terminal lets her choose, goes first.
        self.method.xpago_choose_account = True
        with patch(SEND, return_value=self.intent()) as send:
            self.method.xpago_create_charge({'amount': 25000, 'rule_account_id': self.acc_escrow.id,
                                             'bank_account_id': self.acc_main.id})
        self.assertEqual(send.call_args.kwargs['json']['deposit_account_id'], 'a-main')

    def test_try_the_rules_on_an_order(self):
        self.config.open_ui()
        session = self.config.current_session_id
        order = self.env['pos.order'].create({
            'session_id': session.id, 'amount_tax': 0, 'amount_total': 25200, 'amount_paid': 0, 'amount_return': 0,
            'lines': [(0, 0, {'product_id': self.used.id, 'qty': 1, 'price_unit': 25000, 'price_subtotal': 25000,
                              'price_subtotal_incl': 25000}),
                      (0, 0, {'product_id': self.cleaner.id, 'qty': 1, 'price_unit': 200, 'price_subtotal': 200,
                              'price_subtotal_incl': 200})],
        })
        wizard = self.env['pos.xpago.rule.test'].create({'pos_order_id': order.id, 'split': True})
        self.assertIn('Escrow', wizard.result)
        self.assertIn('Operación', wizard.result)
        self.assertIn('Marketplace al escrow', wizard.result)
