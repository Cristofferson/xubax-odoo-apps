from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.xpago.tests.test_pos_payment_rules import SEND, PosXpagoRulesCommon


@tagged('post_install', '-at_install')
class TestKioskRules(PosXpagoRulesCommon):

    def kiosk_order(self, product):
        self.config.open_ui()
        return self.env['pos.order'].create({
            'session_id': self.config.current_session_id.id, 'amount_tax': 0, 'amount_total': product.list_price,
            'amount_paid': 0, 'amount_return': 0,
            'lines': [(0, 0, {'product_id': product.id, 'qty': 1, 'price_unit': product.list_price,
                              'price_subtotal': product.list_price, 'price_subtotal_incl': product.list_price})],
        })

    def test_kiosk_charge_goes_to_the_account_of_the_rules(self):
        self.method.xpago_bank_account_id = self.acc_terminal
        order = self.kiosk_order(self.used)
        with patch(SEND, return_value=self.intent()) as send:
            result = self.method._payment_request_from_kiosk(order)
        self.assertEqual(send.call_args.kwargs['json']['deposit_account_id'], 'a-escrow')
        self.assertEqual(self.env['pos.xpago.charge'].browse(result['xpago_charge_id']).pos_order_id, order)

    def test_kiosk_without_rules_uses_the_terminal_account(self):
        self.method.xpago_bank_account_id = self.acc_terminal
        self.r_market.use_kiosk = False
        order = self.kiosk_order(self.used)
        with patch(SEND, return_value=self.intent()) as send:
            self.method._payment_request_from_kiosk(order)
        self.assertEqual(send.call_args.kwargs['json']['deposit_account_id'], 'a-terminal')
