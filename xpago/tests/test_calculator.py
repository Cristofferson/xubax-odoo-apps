from unittest.mock import patch

from odoo.tests import HttpCase, tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon

SEND = 'odoo.addons.xpago.models.payment_provider.PaymentProvider._xpago_make_request'


@tagged('post_install', '-at_install')
class TestCalculator(TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A provider of the test company, like the payment tests prepare theirs.
        cls.provider = cls.env['payment.provider'].sudo().search([('code', '=', 'xpago')], limit=1).copy(
            {'company_id': cls.env.company.id})
        cls.provider.write({'xpago_api_key': 'xpk_test_key', 'state': 'test'})
        cls.terminal = cls.env['pos.payment.method'].create({
            'name': 'Terminal mostrador',
            'journal_id': cls.company_data['default_journal_bank'].id,
            'payment_method_type': 'terminal',
            'use_payment_terminal': 'xpago',
            'xpago_provider_id': cls.provider.id,
            'xpago_terminal_serial': 'N750-1',
        })

    def test_info_lists_the_terminals_only_when_charging_is_on(self):
        info = self.env['pos.payment.method'].xpago_calculator_info()
        self.assertTrue(info['charge'])
        self.assertIn(self.terminal.id, [t['id'] for t in info['terminals']])
        self.env.company.xpago_calculator_charge = False
        info = self.env['pos.payment.method'].xpago_calculator_info()
        self.assertFalse(info['charge'])
        self.assertFalse(info['terminals'])

    def test_terminal_named_by_its_registers_and_serial(self):
        self.assertEqual(self.terminal._xpago_calculator_label(), 'Terminal mostrador · terminal …50-1')
        self.env['pos.config'].create({'name': 'Tienda Centro', 'payment_method_ids': [(4, self.terminal.id)]})
        info = self.env['pos.payment.method'].xpago_calculator_info()
        names = {t['id']: t['name'] for t in info['terminals']}
        self.assertEqual(names[self.terminal.id], 'Tienda Centro · terminal …50-1')

    def test_a_charge_from_the_calculator_is_a_charge_without_a_sale(self):
        intent = {'id': 'pi-1', 'status': 'pending', 'expires_at': '2099-01-01T00:10:00.000Z'}
        with patch(SEND, return_value=intent) as api:
            view = self.terminal.xpago_create_charge({'amount': 123.45, 'session_id': False, 'order_uuid': 'calc-1'})
        body = api.call_args.kwargs.get('json') or (api.call_args.args[-1] if api.call_args.args else {})
        self.assertEqual((body.get('amount'), body.get('terminal_serial')), (123.45, 'N750-1'))
        charge = self.env['pos.xpago.charge'].browse(view['id'])
        self.assertFalse(charge.session_id)
        self.assertFalse(charge.pos_order_id)
        self.assertEqual(charge.order_uuid, 'calc-1')


@tagged('post_install', '-at_install')
class TestCalculatorApp(HttpCase):
    """«Install as an app»: the calculator has its own name and icon."""

    def test_installs_as_its_own_app(self):
        manifest = self.url_open('/web/manifest.scoped_app_manifest?app_id=xpago_calculator&path=/odoo/action-xpago.action_xpago_calculator').json()
        self.assertEqual(manifest['name'], 'Calculadora')
        self.assertEqual(manifest['icons'][0]['src'], '/xpago/static/src/img/calculator_terminal.png')
        self.assertEqual(manifest['start_url'], '/odoo/action-xpago.action_xpago_calculator')
        self.assertEqual(self.url_open('/xpago/static/src/img/calculator_terminal.png').status_code, 200)
