from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account_payment.tests.common import AccountPaymentCommon

MOVE_SEND = 'odoo.addons.account.wizard.account_move_send.AccountMoveSend'


@tagged('post_install', '-at_install')
class TestKeepPayment(AccountPaymentCommon):
    """After a card payment (a subscription renewal sends its invoice right away), a stamping or sending problem is
    written on the invoice and given to someone as a task: it never undoes the recorded payment."""

    def make_invoice(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_line_ids': [(0, 0, {'name': 'Plan', 'quantity': 1, 'price_unit': 10, 'tax_ids': []})],
        })
        invoice.action_post()
        return invoice

    def send(self, invoice, keep=True):
        Send = self.env['account.move.send'].with_context(xpago_keep_payment=keep)
        composer = Send.with_context(active_model='account.move', active_ids=invoice.ids).create({})
        return Send._process_send_and_print(invoice, wizard=composer)

    def test_a_failing_stamp_is_noted_not_raised(self):
        invoice = self.make_invoice()
        with patch(f'{MOVE_SEND}._generate_invoice_documents', autospec=True,
                   side_effect=UserError("Falta la categoría UNSPSC")):
            self.send(invoice)
            with self.assertRaises(UserError):
                self.send(invoice, keep=False)
        self.assertIn('UNSPSC', ''.join(invoice.message_ids.mapped('body')))
        self.assertTrue(invoice.activity_ids, 'someone is asked to stamp and send it')

    def test_a_document_error_is_noted_not_raised(self):
        invoice = self.make_invoice()

        def fail(self, invoices_data, allow_fallback_pdf=False):
            for invoice_data in invoices_data.values():
                invoice_data['error'] = "Falta la categoría UNSPSC"

        with patch(f'{MOVE_SEND}._generate_invoice_documents', autospec=True, side_effect=fail):
            self.send(invoice)
        self.assertIn('UNSPSC', ''.join(invoice.message_ids.mapped('body')))
        self.assertTrue(invoice.activity_ids)
