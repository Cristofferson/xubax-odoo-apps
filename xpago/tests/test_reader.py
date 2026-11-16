from odoo.tests import HttpCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestReader(HttpCase):
    """The terminal sends the codes it reads to registers, kiosks and Odoo screens of the same Odoo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['pos.config'].create({'name': 'Caja mostrador'})
        cls.cashier = new_test_user(cls.env, login='xp_reader_cashier', groups='point_of_sale.group_pos_user')
        cls.stranger = new_test_user(cls.env, login='xp_reader_stranger', groups='base.group_user')

    def _messages(self, kind='XPAGO_READER_SCAN'):
        return self.env['bus.bus'].sudo().search([('message', 'like', kind)])

    def test_targets_lists_what_the_terminal_may_send_to(self):
        self.authenticate('xp_reader_cashier', 'xp_reader_cashier')
        targets = self.make_jsonrpc_request('/xpago/reader/targets', {})
        self.assertEqual(targets['db'], self.env.cr.dbname)
        self.assertIn('Caja mostrador', [r['name'] for r in targets['registers']])
        mine = [r for r in targets['registers'] if r['name'] == 'Caja mostrador']
        self.assertFalse(mine[0]['open'], 'its session is not open')
        self.assertNotIn('Caja mostrador', [k['name'] for k in targets['self_order']])

    def test_scan_reaches_the_register(self):
        self.authenticate('xp_reader_cashier', 'xp_reader_cashier')
        answer = self.make_jsonrpc_request('/xpago/reader/scan', {
            'config_id': self.config.id, 'barcode': ' 7501234567890 ', 'device': 'N750'})
        self.assertTrue(answer['ok'])
        messages = self._messages()
        self.assertEqual(len(messages), 1)
        self.assertIn('7501234567890', messages.message)
        self.assertNotIn(' 7501234567890 ', messages.message, 'the code arrives trimmed')

    def test_refuses_bad_codes_and_unknown_registers(self):
        self.authenticate('xp_reader_cashier', 'xp_reader_cashier')
        for barcode in ('', '   ', 'x' * 257):
            answer = self.make_jsonrpc_request('/xpago/reader/scan', {'config_id': self.config.id, 'barcode': barcode})
            self.assertEqual(answer, {'ok': False, 'error': 'bad_barcode'})
        answer = self.make_jsonrpc_request('/xpago/reader/scan', {'config_id': self.config.id + 100000, 'barcode': '1'})
        self.assertEqual(answer, {'ok': False, 'error': 'not_found'})
        self.assertFalse(self._messages())

    def test_needs_access_to_the_register(self):
        self.authenticate('xp_reader_stranger', 'xp_reader_stranger')
        with self.assertRaises(Exception):
            self.make_jsonrpc_request('/xpago/reader/scan', {'config_id': self.config.id, 'barcode': '123'})
        self.assertFalse(self._messages())

    def test_refuses_a_code_made_by_another_database(self):
        self.authenticate('xp_reader_cashier', 'xp_reader_cashier')
        params = {'config_id': self.config.id, 'barcode': '1'}
        self.assertEqual(self.make_jsonrpc_request('/xpago/reader/scan', dict(params, db='otra-base')),
                         {'ok': False, 'error': 'other_db'})
        self.assertTrue(self.make_jsonrpc_request('/xpago/reader/scan', dict(params, db=self.env.cr.dbname))['ok'])

    def test_browser_screen_paired_with_a_qr(self):
        self.authenticate('xp_reader_cashier', 'xp_reader_cashier')
        token = 'a1b2c3d4e5f6a7b8c9d0e1f2'
        pair = self.make_jsonrpc_request('/xpago/reader/pair', {'token': token})
        self.assertTrue(pair['ok'])
        self.assertEqual(pair['db'], self.env.cr.dbname)
        self.assertTrue(self.make_jsonrpc_request('/xpago/reader/scan', {'token': token, 'barcode': 'LOT-0042'})['ok'])
        messages = self._messages('xpago_reader_scan')
        self.assertEqual(len(messages), 1)
        self.assertIn(f'xpago_reader_{token}', messages.channel, 'only the screen that made the key listens')
        for bad in ('', 'short', 'x' * 65, 'abc def ghi jkl'):
            self.assertEqual(self.make_jsonrpc_request('/xpago/reader/pair', {'token': bad}),
                             {'ok': False, 'error': 'not_found'})

    def test_link_explains_itself_in_a_browser(self):
        self.authenticate('xp_reader_cashier', 'xp_reader_cashier')
        page = self.url_open('/xpago/reader/link?token=a1b2c3d4e5f6')
        self.assertEqual(page.status_code, 200)
        self.assertIn('XPago', page.text)

    def test_self_order_kiosk_gets_its_codes_with_its_own_token(self):
        kiosk = self.config
        kiosk._ensure_access_token()
        identity = {'kiosk': 'self_order', 'config_id': kiosk.id, 'access_token': kiosk.access_token}
        first = self.make_jsonrpc_request('/xpago/reader/pull', dict(identity, last=0))
        self.assertEqual(first['codes'], [], 'a kiosk that just opened gets nothing old')
        self.authenticate('xp_reader_cashier', 'xp_reader_cashier')
        for code in ('7500000000017', '7500000000024'):
            self.assertTrue(self.make_jsonrpc_request('/xpago/reader/scan', {
                'kiosk': 'self_order', 'config_id': kiosk.id, 'barcode': code})['ok'])
        self.authenticate(None, None)
        answer = self.make_jsonrpc_request('/xpago/reader/pull', dict(identity, last=first['last']))
        self.assertEqual(answer['codes'], ['7500000000017', '7500000000024'])
        again = self.make_jsonrpc_request('/xpago/reader/pull', dict(identity, last=answer['last']))
        self.assertEqual(again['codes'], [], 'each code arrives once')
        wrong = self.make_jsonrpc_request('/xpago/reader/pull', dict(identity, access_token='not-it', last=first['last']))
        self.assertEqual(wrong, {'last': 0, 'codes': []}, 'another secret gets nothing')

    def test_attendance_kiosk_gets_badges_with_its_key(self):
        if 'attendance_kiosk_key' not in self.env['res.company']._fields:
            self.skipTest('Attendances is not installed')
        company = self.env.company
        key = company.sudo().attendance_kiosk_key
        first = self.make_jsonrpc_request('/xpago/reader/pull', {'kiosk': 'attendance', 'key': key, 'last': 0})
        self.authenticate('xp_reader_cashier', 'xp_reader_cashier')
        targets = self.make_jsonrpc_request('/xpago/reader/targets', {})
        self.assertIn(company.id, [a['id'] for a in targets['attendance']])
        self.assertTrue(self.make_jsonrpc_request('/xpago/reader/scan', {
            'kiosk': 'attendance', 'company_id': company.id, 'barcode': 'EMP-0007'})['ok'])
        other = self.env['res.company'].create({'name': 'Otra empresa'})
        self.assertEqual(self.make_jsonrpc_request('/xpago/reader/scan', {
            'kiosk': 'attendance', 'company_id': other.id, 'barcode': 'EMP-0007'}),
            {'ok': False, 'error': 'not_found'}, 'only companies of this user')
        self.authenticate(None, None)
        answer = self.make_jsonrpc_request('/xpago/reader/pull', {'kiosk': 'attendance', 'key': key, 'last': first['last']})
        self.assertEqual(answer['codes'], ['EMP-0007'])
        self.assertEqual(self.make_jsonrpc_request('/xpago/reader/pull', {'kiosk': 'attendance', 'key': 'nope', 'last': 1}),
                         {'last': 0, 'codes': []})

    def test_bundles(self):
        pos = self.env['ir.qweb']._get_asset_bundle('point_of_sale._assets_pos', css=False, js=True)
        self.assertIn('xpago/static/src/pos/app/reader.js', [f['url'].lstrip('/') for f in pos.files])
        kiosk = self.env['ir.qweb']._get_asset_bundle('pos_self_order.assets', css=False, js=True)
        files = [f['url'].lstrip('/') for f in kiosk.files]
        self.assertIn('xpago/static/src/self_order/reader_self_order.js', files)
        self.assertNotIn('xpago/static/src/pos/app/reader.js', files)
        backend = self.env['ir.qweb']._get_asset_bundle('web.assets_backend', css=False, js=True)
        self.assertIn('xpago/static/src/backend/reader.js', [f['url'].lstrip('/') for f in backend.files])


@tagged('post_install', '-at_install')
class TestSelfCheckout(HttpCase):
    """The customer holds the terminal at a self-order kiosk: it shows what was added, sees the charge arrive, and
    only a manager leaves that mode."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kiosk = cls.env['pos.config'].create({'name': 'Kiosco PFM'})
        cls.product = cls.env['product.product'].create({
            'name': 'Gorra XPago', 'list_price': 150.0, 'barcode': '7500000000017', 'available_in_pos': True,
            'taxes_id': [(6, 0, [])],
        })
        if 'self_order_available' in cls.product._fields:
            cls.product.self_order_available = True
        cls.cashier = new_test_user(cls.env, login='xp_sc_cashier', groups='point_of_sale.group_pos_user')
        cls.boss = new_test_user(cls.env, login='xp_sc_boss', groups='point_of_sale.group_pos_manager')
        # The employees' PIN needs Employees (hr), which XPago does not install.
        if 'hr.employee' in cls.env:
            Employee = cls.env['hr.employee'].sudo()
            cls.boss_employee = Employee.create({'name': 'Gerente', 'user_id': cls.boss.id, 'pin': '4321'})
            cls.clerk_employee = Employee.create({'name': 'Cajera', 'user_id': cls.cashier.id, 'pin': '1111'})

    def test_scan_tells_what_the_kiosk_adds(self):
        self.authenticate('xp_sc_cashier', 'xp_sc_cashier')
        answer = self.make_jsonrpc_request('/xpago/reader/scan', {
            'kiosk': 'self_order', 'config_id': self.kiosk.id, 'barcode': '7500000000017'})
        self.assertEqual(answer['product']['name'], 'Gorra XPago')
        self.assertAlmostEqual(answer['product']['price'], 150.0)
        unknown = self.make_jsonrpc_request('/xpago/reader/scan', {
            'kiosk': 'self_order', 'config_id': self.kiosk.id, 'barcode': '0000000000000'})
        self.assertTrue(unknown['ok'], 'the code still reaches the kiosk')
        self.assertFalse(unknown['product'], 'but the terminal says it is not a product')

    def test_charge_of_the_kiosk(self):
        self.authenticate('xp_sc_cashier', 'xp_sc_cashier')
        self.assertEqual(self.make_jsonrpc_request('/xpago/reader/charge', {'config_id': self.kiosk.id}), {})
        provider = self.env['payment.provider'].sudo().search([('code', '=', 'xpago')], limit=1)
        method = self.env['pos.payment.method'].sudo().create({
            'name': 'XPago', 'use_payment_terminal': 'xpago', 'xpago_provider_id': provider.id, 'xpago_terminal_serial': 'NDB000001'})
        charge = self.env['pos.xpago.charge'].sudo().create({
            'external_id': 'K1-0001', 'amount': 470.0, 'currency_id': self.env.company.currency_id.id,
            'company_id': self.env.company.id, 'payment_method_id': method.id, 'provider_id': provider.id,
            'config_id': self.kiosk.id, 'terminal_app_url': 'xpago-terminal:///charge/pi-1'})
        seen = self.make_jsonrpc_request('/xpago/reader/charge', {'config_id': self.kiosk.id})
        self.assertEqual((seen['id'], seen['state'], seen['app_url']),
                         (charge.id, 'pending', 'xpago-terminal:///charge/pi-1'))
        self.assertEqual(self.make_jsonrpc_request('/xpago/reader/charge', {'config_id': self.kiosk.id, 'after': charge.id}),
                         {}, 'nothing newer')

    def test_only_a_manager_pin_leaves(self):
        self.authenticate('xp_sc_cashier', 'xp_sc_cashier')
        if 'hr.employee' not in self.env:
            self.assertEqual(self.make_jsonrpc_request('/xpago/reader/manager_pin', {'pin': '4321'}), {'ok': False},
                             'without Employees there is no PIN')
            return
        self.assertTrue(self.make_jsonrpc_request('/xpago/reader/manager_pin', {'pin': '4321'})['ok'])
        self.assertFalse(self.make_jsonrpc_request('/xpago/reader/manager_pin', {'pin': '1111'})['ok'], 'not a manager')
        for _n in range(5):
            self.make_jsonrpc_request('/xpago/reader/manager_pin', {'pin': '0000'})
        self.assertEqual(self.make_jsonrpc_request('/xpago/reader/manager_pin', {'pin': '4321'}),
                         {'ok': False, 'error': 'wait'}, 'five wrong tries wait a minute')



@tagged('post_install', '-at_install')
class TestTerminalWake(HttpCase):
    """The Odoo app on the terminal opens the charge app by itself when a register on another computer sends an
    amount, only where the payment method asks for it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cashier = new_test_user(cls.env, login='xp_wake_cashier', groups='point_of_sale.group_pos_user')
        cls.provider = cls.env['payment.provider'].sudo().search([('code', '=', 'xpago')], limit=1)
        cls.method = cls.env['pos.payment.method'].sudo().create({
            'name': 'Tarjeta XPago', 'use_payment_terminal': 'xpago', 'xpago_provider_id': cls.provider.id,
            'xpago_terminal_serial': 'NDC400038415'})

    def _charge(self, ref, **values):
        return self.env['pos.xpago.charge'].sudo().create({
            'external_id': ref, 'amount': 470.0, 'currency_id': self.env.company.currency_id.id,
            'company_id': self.env.company.id, 'payment_method_id': self.method.id, 'provider_id': self.provider.id,
            'terminal_app_url': 'xpago-terminal:///charge/%s' % ref, **values})

    def test_terminal_list(self):
        self.authenticate('xp_wake_cashier', 'xp_wake_cashier')
        answer = self.make_jsonrpc_request('/xpago/reader/terminals', {})
        mine = [t for t in answer['terminals'] if t['serial'] == 'NDC400038415']
        self.assertEqual(len(mine), 1)
        self.assertIn('Tarjeta XPago', mine[0]['names'])
        self.assertFalse(mine[0]['wake'])

    def test_only_when_the_payment_method_asks(self):
        self.authenticate('xp_wake_cashier', 'xp_wake_cashier')
        self._charge('W-1')
        self.assertEqual(self.make_jsonrpc_request('/xpago/reader/wake', {'serial': 'NDC400038415'}), {'enabled': False})
        self.method.xpago_wake_terminal = True
        seen = self.make_jsonrpc_request('/xpago/reader/wake', {'serial': 'ndc400038415'})
        self.assertTrue(seen['enabled'])
        self.assertEqual(seen['app_url'], 'xpago-terminal:///charge/W-1')
        self.assertLess(seen['age'], 60)
        self.assertEqual(self.make_jsonrpc_request('/xpago/reader/wake', {'serial': 'NDC400038415', 'after': seen['id']}),
                         {'enabled': True}, 'the same charge is not opened twice')
        self.assertEqual(self.make_jsonrpc_request('/xpago/reader/wake', {'serial': 'OTRA-TERMINAL'}), {'enabled': False})

    def test_a_charge_already_paid_does_not_open(self):
        self.authenticate('xp_wake_cashier', 'xp_wake_cashier')
        self.method.xpago_wake_terminal = True
        self._charge('W-2', state='confirmed')
        self.assertEqual(self.make_jsonrpc_request('/xpago/reader/wake', {'serial': 'NDC400038415'}), {'enabled': True})
