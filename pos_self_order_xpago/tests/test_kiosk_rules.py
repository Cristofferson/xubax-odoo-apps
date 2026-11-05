from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.pos_xpago.tests.test_payment_rules import SEND, PosXpagoRulesCommon


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
        self.assertEqual(send.call_args.kwargs['json']['bankAccountId'], 'a-escrow')
        self.assertEqual(self.env['pos.xpago.charge'].browse(result['xpago_charge_id']).pos_order_id, order)

    def test_kiosk_without_rules_uses_the_terminal_account(self):
        self.method.xpago_bank_account_id = self.acc_terminal
        self.r_market.use_kiosk = False
        order = self.kiosk_order(self.used)
        with patch(SEND, return_value=self.intent()) as send:
            self.method._payment_request_from_kiosk(order)
        self.assertEqual(send.call_args.kwargs['json']['bankAccountId'], 'a-terminal')

    def test_kiosk_receipt_gets_the_card(self):
        self.config.payment_method_ids |= self.method
        order = self.kiosk_order(self.cleaner)
        with patch(SEND, return_value=self.intent()):
            result = self.method._payment_request_from_kiosk(order)
        charge = self.env['pos.xpago.charge'].browse(result['xpago_charge_id'])
        approved = {**self.intent(), 'status': 'CONFIRMED', 'paymentSummary': {
            'status': 'SUCCESS',
            'payment': {'id': 'pay-1', 'operationCode': 123456, 'chargedAmount': self.cleaner.list_price},
            'paymentTransaction': {'resultCode': 'A1B2C3'},
            'cardInformation': {'fundingSource': 'DEBIT', 'networkType': 'VISA', 'lastFourDigits': '4242',
                                'issuingBank': 'BBVA', 'entryMode': 'CHIP'},
        }}
        sent = []
        with patch(SEND, return_value=approved), \
                patch('odoo.addons.bus.models.bus.BusBus._sendone', lambda bus, target, kind, message: sent.append((kind, message))):
            charge.sudo()._xpago_refresh()
        self.assertIn(order.state, ('paid', 'done'))
        status, = [message for kind, message in sent if kind.endswith('-PAYMENT_STATUS')]
        self.assertEqual(status['payment_result'], 'Success')
        payment, = status['data']['pos.payment']
        self.assertEqual((payment['card_no'], payment['card_type'], payment['payment_method_authcode']),
                         ('4242', 'DEBIT', 'A1B2C3'))
