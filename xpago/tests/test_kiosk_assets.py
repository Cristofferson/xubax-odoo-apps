from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestKioskAssets(TransactionCase):

    def test_kiosk_shows_the_clabe(self):
        bundle = self.env['ir.qweb']._get_asset_bundle('pos_self_order.assets', css=False, js=True)
        files = [file['url'].lstrip('/') for file in bundle.files]
        self.assertIn('xpago/static/src/pos/app/transfer/transfer_utils.js', files)
        self.assertNotIn('xpago/static/src/pos/app/transfer/payment_xpago_transfer.js', files,
                         'the register transfer screen is not the kiosk')
        code = bundle.js().raw.decode()
        self.assertIn('xpago-transfer-start', code)
        self.assertIn('xpago_spei', code, 'the kiosk tells the transfer apart from the card terminal')
        self.assertIn('xpago.SelfOrderPaymentPage', code)

    def test_the_kiosk_gets_the_words_of_xpago(self):
        self.assertIn('xpago', self.env['ir.http']._get_translation_frontend_modules_name())
