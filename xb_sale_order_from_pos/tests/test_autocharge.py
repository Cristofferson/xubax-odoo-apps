# -*- coding: utf-8 -*-
from datetime import timedelta
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.xb_sale_order_from_pos.models.sale_order_layaway import SaleOrder as LayawayOrder

SEND = "odoo.addons.payment.models.payment_transaction.PaymentTransaction._send_payment_request"
POST = "odoo.addons.account_payment.models.payment_transaction.PaymentTransaction._finalize_post_processing"


def _approve(tx):
    tx._set_done()


def _decline(tx):
    tx._set_error("Insufficient funds")


@tagged("post_install", "-at_install")
class TestXbLayawayAutocharge(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({"xb_layaway_days": 30, "xb_layaway_down_percent": 10.0,
                           "xb_layaway_min_payment": 50.0, "xb_layaway_cancel_fee_percent": 10.0})
        cls.partner = cls.env["res.partner"].create({"name": "Auto customer", "email": "auto@example.com"})
        cls.product = cls.env["product.product"].create({
            "name": "Ring", "type": "consu", "list_price": 1000.0, "taxes_id": [(5, 0, 0)]})
        pm = cls.env.ref("payment.payment_method_unknown")
        cls.provider = cls.env["payment.provider"].create({
            "name": "Card provider", "code": "none", "state": "test", "allow_tokenization": True,
            "payment_method_ids": [Command.set(pm.ids)], "company_id": cls.company.id})
        pm.write({"active": True, "support_tokenization": True})
        cls.token = cls.env["payment.token"].create({
            "provider_id": cls.provider.id, "payment_method_id": pm.id, "payment_details": "1168",
            "partner_id": cls.partner.id, "provider_ref": "card-1"})
        cls.today = cls.env["sale.order"]._xb_layaway_today()

    def _pay(self, order, amount):
        tx = self.env["payment.transaction"].create({
            "provider_id": self.provider.id, "payment_method_id": self.token.payment_method_id.id,
            "amount": amount, "currency_id": order.currency_id.id, "partner_id": self.partner.id,
            "operation": "offline", "sale_order_ids": [(6, 0, order.ids)]})
        tx._set_done()
        return tx

    def _layaway(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id, "xb_so_kind": "layaway",
            "user_id": self.env.ref("base.user_admin").id,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1, "price_unit": 1000.0,
                                   "tax_id": [(5, 0, 0)]})],
            **self.env["sale.order"]._xb_layaway_terms(self.company)})
        order.action_confirm()
        self._pay(order, 100.0)  # the down payment
        self.assertEqual(order.amount_unpaid, 900.0)
        self.assertEqual(order.xb_layaway_state, "active")
        return order

    def _wizard(self, order, **vals):
        return self.env["xb.layaway.autocharge"].with_context(default_order_id=order.id).create(vals)

    def test_suggestion_and_setup(self):
        order = self._layaway()
        wizard = self._wizard(order, first_date=self.today + timedelta(days=1))
        self.assertEqual(wizard.token_id, self.token, "the customer's saved card is picked")
        wizard._onchange_every()
        # 30-day term, every 15 days from tomorrow: 2 payments fit -> 450 each.
        self.assertEqual(wizard.amount, 450.0)
        self.assertIn("paid by the deadline", wizard.summary)
        wizard.amount = 100.0
        self.assertIn("still be owed", wizard.summary)
        wizard.amount = 20.0
        with self.assertRaises(UserError, msg="below the minimum payment"):
            wizard.action_confirm()
        wizard.amount = 450.0
        with patch(SEND) as send:
            wizard.action_confirm()
            send.assert_not_called()  # first payment tomorrow: nothing charged today
        self.assertEqual(order.xb_auto_token_id, self.token)
        self.assertEqual(order.xb_auto_next_date, self.today + timedelta(days=1))

    def test_charges_until_paid(self):
        order = self._layaway()
        mails = []
        with patch(SEND, _approve), patch(POST), \
                patch.object(LayawayOrder, "_xb_layaway_send", lambda rec, xmlid: mails.append(xmlid) or True):
            self._wizard(order, amount=500.0, every="fortnight", first_date=self.today).action_confirm()
            self.assertEqual(order.amount_unpaid, 400.0, "first payment charged right away")
            self.assertEqual(order.xb_auto_next_date, self.today + timedelta(days=15))
            self.env["sale.order"]._xb_cron_layaways()
            self.assertEqual(order.amount_unpaid, 400.0, "not due yet")
            order.xb_auto_next_date = self.today
            self.env["sale.order"]._xb_cron_layaways()
        self.assertEqual(order.amount_unpaid, 0.0, "the last payment is only the balance")
        self.assertEqual(order.transaction_ids.filtered("token_id").mapped("amount"), [500.0, 400.0])
        self.assertEqual(order.xb_layaway_state, "paid")
        self.assertFalse(order.xb_auto_token_id, "finished once paid")
        self.assertEqual(mails, ["xb_sale_order_from_pos.mail_template_layaway_autocharge"] * 2)

    def test_declines_retry_then_stop(self):
        order = self._layaway()
        order.write({"xb_auto_token_id": self.token.id, "xb_auto_amount": 300.0,
                     "xb_auto_every": "month", "xb_auto_next_date": self.today})
        with patch(SEND, _decline):
            self.env["sale.order"]._xb_cron_layaways()
            self.assertEqual(order.xb_auto_failures, 1)
            self.assertEqual(order.xb_auto_next_date, self.today + timedelta(days=2), "tried again in 2 days")
            self.assertTrue(order.activity_ids, "the salesperson is told")
            for _i in range(2):
                order.xb_auto_next_date = self.today
                self.env["sale.order"]._xb_cron_layaways()
        self.assertFalse(order.xb_auto_token_id, "stopped after 3 declines")
        self.assertEqual(order.amount_unpaid, 900.0)

    def test_stops_on_expiry_and_cancel(self):
        order = self._layaway()
        order.write({"xb_auto_token_id": self.token.id, "xb_auto_amount": 300.0,
                     "xb_auto_every": "month", "xb_auto_next_date": self.today + timedelta(days=5)})
        with patch.object(LayawayOrder, "_xb_layaway_send", lambda rec, xmlid: True):
            order._xb_layaway_expire()
        self.assertFalse(order.xb_auto_token_id)

    def test_no_card_yet(self):
        order = self._layaway()
        self.token.active = False
        wizard = self._wizard(order)
        self.assertFalse(wizard.token_ids)
        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_template_renders(self):
        order = self._layaway()
        tx = self._pay(order, 200.0)
        tx.token_id = self.token
        body = self.env.ref("xb_sale_order_from_pos.mail_template_layaway_autocharge")._render_field(
            "body_html", order.ids)[order.id]
        self.assertIn("1168", body)
        self.assertIn(order.name, body)
