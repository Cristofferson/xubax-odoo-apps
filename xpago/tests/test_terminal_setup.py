from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.modules.neutralize import get_neutralization_queries
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon

SEND = 'odoo.addons.xpago.models.payment_provider.PaymentProvider._send_api_request'


@tagged('post_install', '-at_install')
class TestTerminalSetup(TestPoSCommon):

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

    def intent(self):
        return {'id': 'pi-1', 'status': 'pending', 'expires_at': '2099-01-01T00:10:00.000Z'}

    def wizard(self, serials=()):
        terminals = {'data': [{'id': f't{n}', 'serial': serial} for n, serial in enumerate(serials)]}
        with patch(SEND, return_value=terminals) as send:
            wizard = self.env['pos.xpago.terminal.setup'].create({})
        self.assertEqual(send.call_args.args, ('GET', '/v1/terminals'))
        return wizard

    def test_terminals_of_the_account_are_offered_without_typing(self):
        for config in self.env['pos.config'].search([]):
            config.payment_method_ids = [(3, m.id) for m in config.payment_method_ids if m.use_payment_terminal == 'xpago']
        self.method.active = False  # no free method to propose: the account's terminals come next
        wizard = self.wizard(serials=['N950-0001', 'NDB400005405'])
        self.assertEqual(wizard.account_serials, 'N950-0001, NDB400005405')
        proposed = wizard.line_ids.filtered('new_serial')
        self.assertEqual(proposed.mapped('new_serial'), ['NDB400005405'], 'only the one Odoo does not have, once')
        self.assertFalse(proposed.create_method, 'created only when the user ticks «Create»')

    def test_without_an_answer_the_serial_is_typed(self):
        with patch(SEND, side_effect=ValidationError('down')):
            wizard = self.env['pos.xpago.terminal.setup'].create({})
        self.assertFalse(wizard.account_serials)
        self.assertTrue(wizard.line_ids)

    def line_of(self, wizard, config):
        return wizard.line_ids.filtered(lambda line: line.config_id == config)

    def test_a_free_terminal_is_proposed_once_and_applied_only_when_confirmed(self):
        for config in self.env['pos.config'].search([]).filtered(lambda c: self.method in c.payment_method_ids):
            config.payment_method_ids -= self.method
        wizard = self.wizard()
        proposed = wizard.line_ids.filtered(lambda line: line.method_id == self.method)
        self.assertEqual(len(proposed), 1, 'a free terminal is proposed to one point of sale only')
        config = proposed.config_id
        self.assertNotIn(self.method, config.payment_method_ids, 'nothing changes before Apply')
        wizard.action_apply()
        self.assertIn(self.method, config.payment_method_ids)

    def test_one_terminal_on_two_points_of_sale_is_warned(self):
        other = self.basic_config.copy({'name': 'Caja 2'})
        wizard = self.wizard()
        self.line_of(wizard, self.basic_config).method_id = self.method
        self.line_of(wizard, other).method_id = self.method
        self.assertIn('N950-0001', wizard.warning_html)
        self.assertIn('one charge at a time', wizard.warning_html)

    def test_a_new_terminal_needs_a_journal_and_an_explicit_create(self):
        wizard = self.wizard()
        line = self.line_of(wizard, self.basic_config)
        line.write({'method_id': False, 'new_serial': 'N750-0099'})
        Method = self.env['pos.payment.method']
        wizard.action_apply()
        self.assertFalse(Method.search([('xpago_terminal_serial', '=', 'N750-0099')]), 'never created silently')
        line.create_method = True
        with self.assertRaises(UserError):
            wizard.action_apply()
        wizard.journal_id = self.company_data['default_journal_bank']
        wizard.action_apply()
        created = Method.search([('xpago_terminal_serial', '=', 'N750-0099')])
        self.assertEqual(len(created), 1)
        self.assertEqual(created.use_payment_terminal, 'xpago')
        self.assertIn(created, self.basic_config.payment_method_ids)
        self.assertNotIn(self.method, self.basic_config.payment_method_ids, 'one XPago terminal per point of sale')

    def test_a_point_of_sale_with_an_open_session_is_left_as_it_is(self):
        config = self.basic_config
        config.payment_method_ids -= self.method
        config.open_ui()
        wizard = self.wizard()
        line = self.line_of(wizard, config)
        line.method_id = self.method
        self.assertTrue(line.has_open_session)
        action = wizard.action_apply()
        self.assertNotIn(self.method, config.payment_method_ids)
        self.assertEqual(action['params']['type'], 'warning')

    def test_neutralized_copy_cancels_waiting_charges_locally(self):
        with patch(SEND, return_value=self.intent()):
            view = self.method.xpago_create_charge({'amount': 10.0, 'order_uuid': 'abcdef12-3456'})
        self.env.flush_all()
        with patch(SEND) as send:
            for query in get_neutralization_queries(['xpago']):
                self.env.cr.execute(query)
        send.assert_not_called()
        self.env.invalidate_all()
        self.assertEqual(self.env['pos.xpago.charge'].browse(view['id']).state, 'cancelled')
