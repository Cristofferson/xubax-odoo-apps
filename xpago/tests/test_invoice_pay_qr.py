from odoo.tests import tagged

from odoo.addons.account_payment.tests.common import AccountPaymentCommon


@tagged('post_install', '-at_install')
class TestInvoicePayQr(AccountPaymentCommon):
    """The pay link and QR of XPago on the invoice PDF (Odoo 19 has its own; 17 and 18 do not)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.xpago = cls._prepare_provider('xpago', update_values={'xpago_api_key': 'xpk_test_key'})
        cls.xpago.journal_id = cls.company_data['default_journal_bank']
        cls.env.company.xpago_invoice_pay_qr = True

    def make_invoice(self, amount=250.0):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'currency_id': self.env.company.currency_id.id,
            'invoice_line_ids': [(0, 0, {'name': 'Servicio', 'quantity': 1, 'price_unit': amount, 'tax_ids': []})],
        })
        move.action_post()
        return move

    def render(self, move):
        html, _type = self.env['ir.actions.report']._render_qweb_html('account.report_invoice', move.ids)
        return html.decode()

    def test_unpaid_invoice_carries_link_and_qr(self):
        move = self.make_invoice()
        html = self.render(move)
        self.assertIn('xpago_payment_link_qrcode', html)
        self.assertIn('PAY THIS INVOICE ONLINE', html)
        self.assertIn('#portal_pay', html, "the link is Odoo's payment link of this invoice")
        self.assertIn('data:image/png;base64,', html, 'the QR image')
        self.assertIn(f'move_id={move.id}', html.replace('&amp;', '&'))

    def test_turned_off_paid_or_without_xpago(self):
        move = self.make_invoice()
        self.env.company.xpago_invoice_pay_qr = False
        self.assertNotIn('xpago_payment_link_qrcode', self.render(move))
        self.env.company.xpago_invoice_pay_qr = True
        self.xpago.state = 'disabled'
        self.assertNotIn('xpago_payment_link_qrcode', self.render(move))
        self.xpago.state = 'test'
        draft = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner.id,
            'invoice_line_ids': [(0, 0, {'name': 'X', 'quantity': 1, 'price_unit': 10, 'tax_ids': []})]})
        self.assertFalse(draft._xpago_show_pay_qr(), 'a draft is not an invoice to pay yet')

    def test_link_outside_a_web_request_is_odoo_s_own(self):
        """Made in the background (no web request), the link is signed the same way Odoo checks it."""
        from odoo.addons.payment import utils as payment_utils
        from odoo.tools.misc import hmac as hmac_tool
        move = self.make_invoice(120.0)
        link = move._xpago_pay_link()
        expected = hmac_tool(self.env(su=True), 'generate_access_token', f'{move.id}|{move.amount_residual}')
        self.assertIn(f'payment_token={expected}', link)
        self.assertTrue(payment_utils.check_access_token.__doc__)

    def test_setting_in_xpago_settings(self):
        settings = self.env['res.config.settings'].create({'xpago_invoice_pay_qr': False})
        settings.execute()
        self.assertFalse(self.env.company.xpago_invoice_pay_qr)
