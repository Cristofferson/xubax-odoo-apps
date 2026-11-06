from unittest.mock import patch

import requests

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.xpago.tests.common import XpagoCommon

SEND = 'odoo.addons.payment.models.payment_provider.PaymentProvider._send_api_request'


class XpagoRulesCommon(XpagoCommon):
    """Rules of a jewelry shop: 12 months on jewelry over $5,000, the marketplace pieces to the escrow account with
    up to 6 months, and anything under $1,000 single payment to the main account."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Account = cls.env['payment.xpago.bank.account']
        cls.acc_main = Account.create({'provider_id': cls.provider.id, 'xpago_id': 'a-main', 'name': 'Operación'})
        cls.acc_escrow = Account.create({'provider_id': cls.provider.id, 'xpago_id': 'a-escrow', 'name': 'Escrow'})
        cls.categ_jewel = cls.env['product.category'].create({'name': 'Joyería'})
        cls.categ_diamond = cls.env['product.category'].create({'name': 'Diamantes', 'parent_id': cls.categ_jewel.id})
        cls.tag_market = cls.env['product.tag'].create({'name': 'Marketplace'})
        cls.ring = cls.env['product.product'].create({'name': 'Anillo', 'categ_id': cls.categ_diamond.id, 'list_price': 30000})
        cls.used = cls.env['product.product'].create({'name': 'Anillo seminuevo', 'list_price': 25000,
                                                      'product_tag_ids': [(6, 0, cls.tag_market.ids)]})
        cls.cleaner = cls.env['product.product'].create({'name': 'Limpiador', 'list_price': 200})
        Rule = cls.env['payment.xpago.rule']
        cls.r_jewel = Rule.create({'name': '12 MSI en joyería', 'sequence': 10, 'categ_ids': [(6, 0, cls.categ_jewel.ids)],
                                   'msi_mode': 'terms', 'terms': '3, 6, 12', 'price_min': 5000})
        cls.r_market = Rule.create({'name': 'Marketplace al escrow', 'sequence': 5, 'tag_ids': [(6, 0, cls.tag_market.ids)],
                                    'msi_mode': 'terms', 'terms': '3, 6', 'bank_account_id': cls.acc_escrow.id})
        cls.r_cheap = Rule.create({'name': 'Menos de $1,000 de contado', 'sequence': 20, 'price_max': 1000, 'msi_mode': 'none',
                                   'bank_account_id': cls.acc_main.id})

    def plan(self, products, split=False, channel='online', config=None):
        lines = [{'product': p, 'unit_price': p.list_price, 'amount': p.list_price} for p in products]
        return self.env['payment.xpago.rule']._xpago_plan(
            self.env.company, channel, lines, sum(line['amount'] for line in lines), config=config, split=split)


@tagged('post_install', '-at_install')
class TestPaymentRules(XpagoRulesCommon):

    def test_category_children_and_price(self):
        part, = self.plan([self.ring])
        self.assertEqual(part['terms'], [1, 3, 6, 12])
        self.assertFalse(part['account'])

    def test_months_only_if_every_product_allows_them(self):
        part, = self.plan([self.ring, self.used])
        self.assertEqual(part['terms'], [1, 3, 6])
        part, = self.plan([self.ring, self.cleaner])
        self.assertEqual(part['terms'], [1], 'the cleaner is single payment only')

    def test_free_lines_do_not_decide(self):
        """Shipping at $0 or a gift fits the "up to $1,000" rule but is not sold: the ring keeps its months."""
        lines = [{'product': self.ring, 'unit_price': 30000, 'amount': 30000},
                 {'product': self.cleaner, 'unit_price': 0, 'amount': 0}]
        part, = self.env['payment.xpago.rule']._xpago_plan(self.env.company, 'online', lines, 30000)
        self.assertEqual(part['terms'], [1, 3, 6, 12])
        self.assertFalse(part['account'])

    def test_account_by_priority(self):
        part, = self.plan([self.used, self.cleaner])
        self.assertEqual(part['account'], self.acc_escrow, 'the marketplace rule is placed higher')

    def test_split_by_account_and_months(self):
        parts = self.plan([self.used, self.cleaner, self.ring], split=True)
        by_account = {(p['account'].name or ''): p for p in parts}
        self.assertEqual(len(parts), 3)
        self.assertEqual(by_account['Escrow']['amount'], 25000)
        self.assertEqual(by_account['Escrow']['terms'], [1, 3, 6])
        self.assertEqual(by_account['Operación']['amount'], 200)
        self.assertEqual(by_account['']['terms'], [1, 3, 6, 12])

    def test_online_switch_dates_and_amounts(self):
        self.r_market.use_online = False
        part, = self.plan([self.used])
        self.assertFalse(part['account'])
        self.r_market.use_online = True
        self.r_market.date_to = '2000-01-01'
        part, = self.plan([self.used])
        self.assertFalse(part['account'])
        self.r_market.write({'date_to': False, 'amount_min': 50000})
        part, = self.plan([self.used])
        self.assertFalse(part['account'], 'the sale is under the amount of the rule')

    def test_wrong_rules_are_refused(self):
        Rule = self.env['payment.xpago.rule']
        with self.assertRaises(ValidationError):
            Rule.create({'name': 'Mal', 'msi_mode': 'terms', 'terms': '3, 99'})
        with self.assertRaises(ValidationError):
            Rule.create({'name': 'Nada', 'msi_mode': 'keep'})

    def test_products_that_fit(self):
        self.assertEqual(self.r_jewel.product_count, 1)
        self.assertEqual(self.r_market.product_count, 1)
        self.assertEqual(self.r_cheap.product_count, 0, 'a rule by price names no products')


@tagged('post_install', '-at_install')
class TestPaymentRulesOnline(XpagoRulesCommon):

    def invoice_tx(self, products):
        if 'invoice_ids' not in self.env['payment.transaction']:
            self.skipTest('needs account_payment')
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_line_ids': [(0, 0, {'product_id': p.id, 'quantity': 1, 'price_unit': p.list_price, 'tax_ids': [(6, 0, [])]})
                                 for p in products],
        })
        return self._create_transaction('redirect', currency_id=invoice.currency_id.id, amount=invoice.amount_total,
                                        invoice_ids=[(6, 0, invoice.ids)], reference=f'XP-RULES-{invoice.id}')

    def test_checkout_carries_the_terms_and_account_of_the_rules(self):
        tx = self.invoice_tx([self.used, self.ring])
        with patch(SEND, return_value=self.checkout) as send:
            tx._get_specific_rendering_values(None)
        payload = send.call_args.kwargs['json']
        self.assertEqual(payload['installments'], [1, 3, 6])
        self.assertEqual(payload['deposit_account_id'], 'a-escrow')

    def test_rule_account_goes_before_the_invoice_account(self):
        self.provider.xpago_invoice_bank_account_id = self.acc_main
        tx = self.invoice_tx([self.ring])
        payload = tx._xpago_prepare_checkout_payload()
        self.assertEqual(payload['deposit_account_id'], 'a-main', 'the ring rule names no account: the invoice account')
        self.assertEqual(payload['installments'], [1, 3, 6, 12])
        tx = self.invoice_tx([self.used])
        self.assertEqual(tx._xpago_prepare_checkout_payload()['deposit_account_id'], 'a-escrow')

    def test_rule_terms_narrow_the_terms_of_the_amount(self):
        self.provider.xpago_installment_rule_ids = [(0, 0, {'min_amount': 0, 'terms': '3, 6, 9, 12, 18'})]
        tx = self.invoice_tx([self.ring])
        self.assertEqual(tx._xpago_prepare_checkout_payload()['installments'], [1, 3, 6, 12])

    def test_months_not_active_in_xpago_are_retried_without_them(self):
        tx = self.invoice_tx([self.ring])
        payloads = []

        def send(method, endpoint, json=None, **kwargs):
            payloads.append(json)
            if len(payloads) == 1:
                response = requests.Response()
                response.status_code = 400
                response._content = (b'{"error": {"code": "installments_unavailable", "message": "Not active",'
                                     b' "details": {"available": [1, 3, 6], "unavailable": [12]}}}')
                try:
                    response.raise_for_status()
                except requests.exceptions.HTTPError:
                    raise ValidationError('The payment provider rejected the request.')  # noqa: B904 - as Odoo does
            return self.checkout

        with patch(SEND, side_effect=send):
            tx._get_specific_rendering_values(None)
        self.assertEqual([p['installments'] for p in payloads], [[1, 3, 6, 12], [1, 3, 6]])
        self.assertEqual(tx.provider_reference, self.checkout_id)
