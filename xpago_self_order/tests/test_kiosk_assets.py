from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestKioskAssets(TransactionCase):

    def test_kiosk_receipt_carries_the_card_voucher(self):
        bundle = self.env['ir.qweb']._get_asset_bundle('pos_self_order.assets', css=False, js=True)
        files = [file['url'].lstrip('/') for file in bundle.files]
        self.assertIn('xpago/static/src/app/order_receipt_voucher.js', files)
        self.assertIn('xpago/static/src/app/order_receipt_voucher.xml', files)
        self.assertNotIn('xpago/static/src/app/payment_xpago.js', files, 'the register terminal is not the kiosk')
        code = bundle.js().raw.decode()
        self.assertIn('xpagoVoucherLines', code)
        self.assertIn('xpago.OrderReceipt', code)
