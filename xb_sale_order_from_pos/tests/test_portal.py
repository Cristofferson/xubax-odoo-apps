# -*- coding: utf-8 -*-
# «My layaway» on Odoo 18: the page takes the amount, checks it against the terms and
# shows Odoo's own payment form for it; the transaction route refuses other amounts.
from odoo.tests import HttpCase, tagged
from odoo.tests.common import JsonRpcException


@tagged("post_install", "-at_install")
class TestXbLayawayPortal(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        company.write({"xb_layaway_days": 30, "xb_layaway_down_percent": 10.0,
                       "xb_layaway_min_payment": 50.0, "xb_layaway_cancel_fee_percent": 10.0})
        partner = cls.env["res.partner"].create({"name": "Portal customer", "email": "portal@example.com"})
        product = cls.env["product.product"].create({
            "name": "Ring", "type": "consu", "list_price": 1000.0, "taxes_id": [(5, 0, 0)]})
        cls.order = cls.env["sale.order"].create({
            "partner_id": partner.id, "xb_so_kind": "layaway",
            "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": 1, "price_unit": 1000.0,
                                   "tax_id": [(5, 0, 0)]})],
            **cls.env["sale.order"]._xb_layaway_terms(company)})
        cls.order.action_confirm()
        cls.order.amount_unpaid = 900.0  # the down payment was paid
        cls.token = cls.order._portal_ensure_token()

    def _page(self, amount):
        url = "/my/orders/%s?access_token=%s&payment_amount=%s" % (self.order.id, self.token, amount)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        return response.text

    def test_my_layaway_payment(self):
        self.assertEqual(self.order.xb_layaway_state, "active")
        page = self._page(200)
        self.assertIn('id="xb_layaway"', page)
        self.assertIn("o_xb_layaway_payment", page, "the payment form is shown for the amount")
        page = self._page(20)
        self.assertNotIn("o_xb_layaway_payment", page, "below the minimum payment")
        self.assertIn("The minimum payment on", page)

    def test_transaction_amount_is_checked(self):
        with self.assertRaises(JsonRpcException) as caught:
            self.make_jsonrpc_request(
                "/my/orders/%s/transaction" % self.order.id,
                {"access_token": self.token, "amount": 10.0},
            )
        self.assertIn("ValidationError", str(caught.exception))
