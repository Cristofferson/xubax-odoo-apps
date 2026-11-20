from unittest.mock import patch

from odoo.tests import HttpCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestPriceChecker(HttpCase):
    """The customer scans a product and sees its price, as the chosen Point of Sale sells it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['pos.config'].create({'name': 'Tienda centro'})
        cls.config.action_price_checker_new_link()
        cls.token = cls.config.sudo().price_checker_token
        cls.cashier = new_test_user(cls.env, login='xpc_cashier', groups='base.group_user,point_of_sale.group_pos_user')
        cls.stranger = new_test_user(cls.env, login='xpc_stranger', groups='base.group_user')
        cls.ring = cls.env['product.product'].create({
            'name': 'Anillo solitario', 'barcode': '7500000000017', 'default_code': 'ANI-01', 'list_price': 12000,
            'taxes_id': [(5, 0, 0)]})

    def lookup(self, barcode, token=None, **extra):
        return self.make_jsonrpc_request('/price-checker/lookup', dict(
            {'config_id': self.config.id, 'token': token or self.token, 'barcode': barcode}, **extra))

    def test_page_opens_with_its_key_only(self):
        self.assertEqual(self.url_open(f'/price-checker/{self.config.id}/{self.token}').status_code, 200)
        self.assertEqual(self.url_open(f'/price-checker/{self.config.id}/wrong-key-123').status_code, 404)
        self.assertIn(self.token, self.config.price_checker_url)

    def test_name_and_price(self):
        answer = self.lookup('7500000000017')
        self.assertTrue(answer['found'])
        self.assertEqual((answer['name'], answer['price']), ('[ANI-01] Anillo solitario', 12000))
        self.assertFalse(answer['before_text'], 'no discount')
        self.assertFalse(answer['months_text'], 'nothing gives months without a payment module')
        self.assertTrue(self.lookup(' ani-01 ')['found'], 'the internal reference works too')

    def test_wrong_key_or_unknown_code(self):
        self.assertEqual(self.lookup('7500000000017', token='wrong-key-123'), {'found': False, 'error': 'not_found'})
        self.assertEqual(self.lookup('0000'), {'found': False, 'error': 'no_product'})
        old = self.token
        self.config.action_price_checker_new_link()
        self.assertEqual(self.lookup('7500000000017', token=old)['found'], False, 'a new link stops the old one')

    def test_discount_of_the_pricelist(self):
        Item = self.env['product.pricelist.item']
        rule = {'applied_on': '3_global', 'compute_price': 'percentage', 'percent_price': 20} \
            if 'percent_price' in Item._fields else {'applied_on': '3_global', 'compute_price': 'discount', 'price_discount': 20}
        pricelist = self.env['product.pricelist'].create({'name': 'Promo', 'item_ids': [(0, 0, rule)]})
        self.config.write({'pricelist_id': pricelist.id, 'available_pricelist_ids': [(4, pricelist.id)]})
        answer = self.lookup('7500000000017')
        self.assertEqual(answer['price'], 9600)
        self.assertTrue(answer['before_text'])
        self.assertEqual(answer['discount_text'], '-20 %')

    def test_stock_without_numbers(self):
        if 'free_qty' not in self.env['product.product']._fields:
            self.skipTest('Inventory is not installed')
        storable = {'is_storable': True} if 'is_storable' in self.env['product.product']._fields else {'detailed_type': 'product'}
        chain = self.env['product.product'].create(dict({'name': 'Cadena', 'barcode': '7500000000031', 'list_price': 500}, **storable))
        self.assertIs(self.lookup('7500000000031')['in_stock'], False)
        self.env['stock.quant']._update_available_quantity(chain, self.config._price_checker_warehouse().lot_stock_id, 3)
        answer = self.lookup('7500000000031')
        self.assertIs(answer['in_stock'], True)
        self.assertNotIn('3', answer['stock_text'])
        self.config.price_checker_show_stock = False
        self.assertIsNone(self.lookup('7500000000031')['in_stock'])

    def test_months_without_interest_from_a_payment_module(self):
        with patch.object(type(self.env['pos.config']), '_price_checker_months', return_value=12):
            answer = self.lookup('7500000000017')
        self.assertIn('12', answer['months_text'])
        self.assertIn('1,000.00', answer['months_text'], '12,000 in 12 months')

    def test_app_with_an_odoo_session(self):
        self.authenticate('xpc_cashier', 'xpc_cashier')
        answer = self.make_jsonrpc_request('/price-checker/lookup-user', {'config_id': self.config.id, 'barcode': '7500000000017'})
        self.assertTrue(answer['found'])
        self.assertEqual(self.make_jsonrpc_request('/price-checker/lookup-user', {
            'config_id': self.config.id, 'barcode': '1', 'db': 'otra-base'}), {'found': False, 'error': 'other_db'})
        self.authenticate('xpc_stranger', 'xpc_stranger')
        with self.assertRaises(Exception):
            self.make_jsonrpc_request('/price-checker/lookup-user', {'config_id': self.config.id, 'barcode': '7500000000017'})

    def test_months_of_the_xpago_payment_rules(self):
        if 'payment.xpago.rule' not in self.env:
            self.skipTest('XPago is not installed')
        self.env['payment.xpago.rule'].create({
            'name': 'Meses en anillos', 'msi_mode': 'terms', 'terms': '3,6,12', 'product_ids': [(6, 0, self.ring.ids)]})
        self.assertIn('12', self.lookup('7500000000017')['months_text'])
        self.config.price_checker_show_months = False
        self.assertFalse(self.lookup('7500000000017')['months_text'])

    def test_install_as_app(self):
        """«Install as an app» opens Odoo's install page for this register's link, with the app's own name."""
        action = self.config.action_price_checker_install()
        settings = self.env['res.config.settings'].create({'pos_config_id': self.config.id})
        self.assertEqual(settings.action_price_checker_install()['url'], action['url'])
        self.assertTrue(action['url'].startswith('/scoped_app?app_id=xb_price_checker'))
        self.assertIn(f'price-checker%2F{self.config.id}%2F{self.token}', action['url'])
        manifest = self.url_open('/web/manifest.scoped_app_manifest?app_id=xb_price_checker&path=x').json()
        self.assertEqual(manifest['name'], 'Verificador de precios')
