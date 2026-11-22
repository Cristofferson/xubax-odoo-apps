from unittest import SkipTest
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account_payment.tests.common import AccountPaymentCommon

SEND = 'odoo.addons.xpago.models.payment_provider.PaymentProvider._send_api_request'
MOVE_SEND = 'odoo.addons.account.models.account_move_send.AccountMoveSend'


@tagged('post_install', '-at_install')
class TestRenewal(AccountPaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'sale.subscription.plan' not in cls.env:
            raise SkipTest("the Subscriptions app is not installed")
        cls.enable_process_patcher = cls.enable_post_process_patcher = False
        cls.xpago = cls._prepare_provider('xpago', update_values={'xpago_api_key': 'xpk_test_key'})
        cls.xpago.journal_id = cls.company_data['default_journal_bank']
        cls.partner.write({'email': 'cliente@ejemplo.mx', 'country_id': cls.env.ref('base.mx').id})
        cls.token = cls.env['payment.token'].create({
            'provider_id': cls.xpago.id, 'payment_method_id': cls.xpago.payment_method_ids[:1].id,
            'partner_id': cls.partner.id, 'provider_ref': 'pm-1', 'payment_details': '4242',
        })
        plan = cls.env['sale.subscription.plan'].sudo().create(
            {'name': 'Mensual', 'billing_period_value': 1, 'billing_period_unit': 'month'})
        product = cls.env['product.product'].sudo().create(
            {'name': 'Plan', 'type': 'service', 'recurring_invoice': True, 'list_price': 10})
        cls.order = cls.env['sale.order'].sudo().create({
            'partner_id': cls.partner.id, 'plan_id': plan.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 1, 'price_unit': 10, 'tax_ids': []})],
        })
        cls.order.action_confirm()
        cls.order.payment_token_id = cls.token

    def charge_paid(self):
        def send(provider, method, path, **kwargs):
            body = kwargs.get('json') or {}
            return {'id': 'cp-1', 'status': 'paid', 'amount': body.get('amount'),
                    'currency': self.env.company.currency_id.name}
        return patch(SEND, autospec=True, side_effect=send)

    def renew(self):
        self.order.next_invoice_date = fields.Date.today()
        with self.charge_paid(), \
                patch(f'{MOVE_SEND}._get_default_extra_edis', autospec=True, return_value={'stamp'}), \
                patch(f'{MOVE_SEND}._check_sending_data', autospec=True,
                      side_effect=UserError("Falta la categoría UNSPSC")):
            invoice = self.order._create_recurring_invoice()
            tx = self.order.transaction_ids.filtered(lambda t: t.state == 'done')[-1:]
            tx._post_process_with_lock()
        return invoice, tx

    def test_payment_is_recorded_when_the_invoice_cannot_be_sent(self):
        invoice, tx = self.renew()
        self.assertTrue(tx.is_post_processed)
        self.assertTrue(tx.payment_id, 'the payment is recorded')
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))
        self.assertIn('UNSPSC', ''.join(invoice.message_ids.mapped('body')))
        self.assertTrue(invoice.activity_ids, 'someone is asked to stamp and send it')
