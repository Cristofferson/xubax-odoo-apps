from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged

from odoo.addons.xpago_pos.tests import test_pos_payment_rules

SEND = test_pos_payment_rules.SEND


@tagged('post_install', '-at_install')
class TestKioskTimeout(test_pos_payment_rules.PosXpagoRulesCommon):

    def kiosk_order(self, product):
        self.config.open_ui()
        return self.env['pos.order'].create({
            'session_id': self.config.current_session_id.id, 'amount_tax': 0, 'amount_total': product.list_price,
            'amount_paid': 0, 'amount_return': 0,
            'lines': [(0, 0, {'product_id': product.id, 'qty': 1, 'price_unit': product.list_price,
                              'price_subtotal': product.list_price, 'price_subtotal_incl': product.list_price})],
        })

    def kiosk_charge(self, age_seconds):
        order = self.kiosk_order(self.cleaner)
        with patch(SEND, return_value=self.intent()):
            result = self.method._payment_request_from_kiosk(order)
        charge = self.env['pos.xpago.charge'].browse(result['xpago_charge_id'])
        self.env.cr.execute("UPDATE pos_xpago_charge SET create_date = %s WHERE id = %s",
                            [fields.Datetime.now() - timedelta(seconds=age_seconds), charge.id])
        charge.invalidate_recordset(['create_date'])
        return charge

    def run_cron(self):
        with patch(SEND, return_value={'id': 'pi-1', 'status': 'canceled'}) as send:
            self.env['pos.xpago.charge']._xpago_cancel_abandoned_kiosk_charges()
        return send

    def test_the_kiosk_gets_its_timeout(self):
        self.assertEqual(self.config.xpago_kiosk_timeout, 120)
        fields_loaded = self.env['pos.config']._load_pos_self_data_fields(self.config)
        self.assertTrue(not fields_loaded or 'xpago_kiosk_timeout' in fields_loaded)

    def test_an_abandoned_kiosk_charge_frees_the_terminal(self):
        charge = self.kiosk_charge(age_seconds=400)
        send = self.run_cron()
        self.assertEqual(send.call_args.args, ('POST', '/v1/terminal-charges/pi-1/cancel'))
        self.assertEqual(charge.state, 'cancelled')

    def test_a_recent_kiosk_charge_is_left_waiting(self):
        charge = self.kiosk_charge(age_seconds=30)
        send = self.run_cron()
        send.assert_not_called()
        self.assertEqual(charge.state, 'pending')

    def test_timeout_zero_never_cancels(self):
        self.config.xpago_kiosk_timeout = 0
        charge = self.kiosk_charge(age_seconds=4000)
        self.run_cron().assert_not_called()
        self.assertEqual(charge.state, 'pending')
