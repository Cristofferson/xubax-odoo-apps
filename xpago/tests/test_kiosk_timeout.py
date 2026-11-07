from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon

SEND = 'odoo.addons.xpago.models.payment_provider.PaymentProvider._xpago_make_request'


@tagged('post_install', '-at_install')
class TestKioskTimeout(TestPoSCommon):
    """A kiosk charge nobody pays frees the terminal."""

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

    def kiosk_charge(self, age_seconds):
        with patch(SEND, return_value=self.intent()):
            status = self.method._payment_request_from_kiosk(self.order)
        charge = self.env['pos.xpago.charge'].sudo().browse(status['xpago_charge_id'])
        self.env.cr.execute("UPDATE pos_xpago_charge SET create_date = %s WHERE id = %s",
                            [fields.Datetime.now() - timedelta(seconds=age_seconds), charge.id])
        charge.invalidate_recordset(['create_date'])
        return charge

    def run_cron(self):
        with patch(SEND, return_value={'id': 'pi-k1', 'status': 'canceled'}) as send:
            self.env['pos.xpago.charge']._xpago_cancel_abandoned_kiosk_charges()
        return send

    def test_the_kiosk_gets_its_timeout(self):
        self.assertEqual(self.config.xpago_kiosk_timeout, 120)
        self.assertEqual(self.config._get_self_ordering_data()['config']['xpago_kiosk_timeout'], 120)

    def test_an_abandoned_kiosk_charge_frees_the_terminal(self):
        charge = self.kiosk_charge(age_seconds=400)
        send = self.run_cron()
        self.assertEqual(send.call_args.args[:2], ('POST', '/v1/terminal-charges/pi-k1/cancel'))
        self.assertEqual(charge.state, 'cancelled')

    def test_a_recent_kiosk_charge_is_left_waiting(self):
        charge = self.kiosk_charge(age_seconds=30)
        self.run_cron().assert_not_called()
        self.assertEqual(charge.state, 'pending')

    def test_timeout_zero_never_cancels(self):
        self.config.xpago_kiosk_timeout = 0
        charge = self.kiosk_charge(age_seconds=4000)
        self.run_cron().assert_not_called()
        self.assertEqual(charge.state, 'pending')
