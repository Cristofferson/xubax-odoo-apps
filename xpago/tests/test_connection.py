from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.modules.neutralize import get_neutralization_queries
from odoo.tests import tagged

from odoo.addons.xpago import const
from odoo.addons.xpago.tests.common import XpagoCommon

SEND = 'odoo.addons.xpago.models.payment_provider.PaymentProvider._xpago_make_request'


@tagged('post_install', '-at_install')
class TestXpagoConnection(XpagoCommon):

    def test_panel_starts_unchecked_and_reads_the_environment(self):
        self.assertEqual(self.provider.xpago_connection_state, 'unknown')
        self.assertEqual(self.provider.xpago_environment, 'test')
        self.provider.write({'xpago_api_key': 'xpk_live_key', 'state': 'enabled'})
        self.assertEqual(self.provider.xpago_environment, 'live')

    def test_connection_button_shows_the_account(self):
        with patch(SEND, return_value={'id': 'org-1', 'name': 'LAMUR', 'legal_name': 'LAMUR SA'}) as send:
            action = self.provider.action_xpago_test_connection()
        self.assertEqual(send.call_args.args, ('GET', '/v1/account'))
        self.assertEqual(action['params']['type'], 'success')
        self.provider.invalidate_recordset()
        self.assertEqual(self.provider.xpago_connection_state, 'ok')
        self.assertEqual(self.provider.xpago_account_name, 'LAMUR')
        self.assertTrue(self.provider.xpago_last_ok_at)

    def test_connection_button_shows_the_error(self):
        with patch(SEND, side_effect=ValidationError('No connection with XPago.')):
            action = self.provider.action_xpago_test_connection()
        self.assertEqual(action['params']['type'], 'danger')
        self.provider.invalidate_recordset()
        self.assertEqual(self.provider.xpago_connection_state, 'error')
        self.assertIn('No connection', self.provider.xpago_last_error)

    def test_a_later_success_clears_the_error(self):
        with patch(SEND, side_effect=ValidationError('down')):
            self.provider.action_xpago_test_connection()
        with patch(SEND, return_value={'name': 'LAMUR'}):
            self.provider.action_xpago_test_connection()
        self.provider.invalidate_recordset()
        self.assertEqual(self.provider.xpago_connection_state, 'ok')

    def test_noting_calls_never_breaks_a_request(self):
        # In tests the passive note is skipped (it writes in its own transaction); outside, a failure is only logged.
        self.provider._xpago_note_call(True)
        self.provider._xpago_note_call(False, 'down')

    def test_neutralized_copy_never_charges(self):
        tx = self._create_transaction('redirect', currency_id=self.currency.id, state='pending')
        self.provider.state = 'test'
        self.provider._xpago_save_status(ok=True, account_name='LAMUR')
        self.env.flush_all()
        for query in get_neutralization_queries(['payment', 'xpago']):
            self.env.cr.execute(query)
        self.env.invalidate_all()
        self.assertFalse(self.provider.xpago_api_key)
        self.assertEqual(self.provider.state, 'disabled')
        self.assertTrue(self.provider.xpago_neutralized)
        self.assertEqual(tx.state, 'cancel')
        self.assertEqual(self.provider.xpago_connection_state, 'unknown')

    def test_a_new_key_ends_the_neutralized_mark(self):
        self.provider.write({'xpago_neutralized': True})
        self.provider.xpago_api_key = 'xpk_test_other'
        self.assertFalse(self.provider.xpago_neutralized)

    def test_backup_addresses_are_on_xpago_com_mx(self):
        self.assertEqual(const.API_URLS[0], 'https://api.xpago.mx')
        self.assertEqual(const.API_URLS[1:], tuple(f'https://n{n}.xpago.com.mx' for n in (1, 2, 3)))
