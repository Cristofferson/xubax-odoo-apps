# -*- coding: utf-8 -*-
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged

from odoo.addons.xb_sale_order_from_pos.models.sale_order_layaway import SaleOrder as LayawayOrder


@tagged("post_install", "-at_install")
class TestXbLayaway(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            "xb_layaway_days": 30,
            "xb_layaway_down_percent": 10.0,
            "xb_layaway_min_payment": 50.0,
            "xb_layaway_cancel_fee_percent": 10.0,
            "xb_layaway_notify_customer": True,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Layaway customer", "email": "layaway@example.com"})
        cls.product = cls.env["product.product"].create({
            "name": "Ring", "type": "consu", "is_storable": True, "list_price": 1000.0, "taxes_id": [(5, 0, 0)],
        })
        cls.today = cls.env["sale.order"]._xb_layaway_today()

    def _layaway(self, paid=0.0, **vals):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "xb_so_kind": "layaway",
            "user_id": self.env.ref("base.user_admin").id,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1, "price_unit": 1000.0, "tax_ids": [(5, 0, 0)]})],
            **self.env["sale.order"]._xb_layaway_terms(self.company),
            **vals,
        })
        order.action_confirm()
        # Stand-in for the payments (POS down payments, invoices, online payments)
        # that pos_sale's stored balance is computed from.
        order.amount_unpaid = order.amount_total - paid
        return order

    def test_terms_come_from_the_company(self):
        order = self._layaway(paid=100)
        self.assertEqual(order.xb_layaway_deadline, self.today + timedelta(days=30))
        self.assertEqual(order.xb_layaway_min_payment, 50.0)
        self.assertEqual(order.xb_layaway_state, "active")
        self.company.xb_layaway_min_payment = 80.0
        self.assertEqual(order.xb_layaway_min_payment, 50.0, "an accepted layaway keeps its terms")

    def test_states(self):
        order = self._layaway(paid=100)
        self.assertEqual(order.xb_layaway_paid, 100.0)
        self.assertAlmostEqual(order.xb_layaway_progress, 10.0)
        order.amount_unpaid = 0.0
        self.assertEqual(order.xb_layaway_state, "paid")
        other = self._layaway(paid=100)
        other.xb_layaway_expired_on = self.today
        self.assertEqual(other.xb_layaway_state, "expired")
        not_layaway = self._layaway(paid=100, xb_so_kind="order")
        self.assertFalse(not_layaway.xb_layaway_state)

    def test_payment_rules(self):
        first = self._layaway(paid=0.0)
        first.write({"state": "sale"})
        self.assertTrue(first._xb_layaway_check_payment(50.0), "below the 10% down payment")
        self.assertFalse(first._xb_layaway_check_payment(100.0))
        later = self._layaway(paid=100.0)
        self.assertTrue(later._xb_layaway_check_payment(30.0), "below the minimum payment")
        self.assertFalse(later._xb_layaway_check_payment(50.0))
        self.assertTrue(later._xb_layaway_check_payment(901.0), "more than the balance")
        later.amount_unpaid = 20.0
        self.assertFalse(later._xb_layaway_check_payment(20.0), "settling the balance is always fine")
        later.xb_layaway_expired_on = self.today
        self.assertTrue(later._xb_layaway_check_payment(20.0), "an expired layaway takes no payment")

    def test_reminder_is_an_automation_rule(self):
        rule = self.env.ref("xb_sale_order_from_pos.automation_layaway_reminder")
        self.assertEqual((rule.trigger, rule.trg_date_range, rule.trg_date_range_mode, rule.trg_date_range_type),
                         ("on_time", 3, "before", "day"))
        self.assertEqual(rule.trg_date_id.name, "xb_layaway_deadline")
        self.assertEqual(rule.action_server_ids.template_id,
                         self.env.ref("xb_sale_order_from_pos.mail_template_layaway_reminder"))
        due = self._layaway(paid=200.0)
        due.xb_layaway_deadline = self.today + timedelta(days=2)
        later = self._layaway(paid=200.0)
        later.xb_layaway_deadline = self.today + timedelta(days=20)
        Mail = self.env["mail.mail"].sudo()
        before = Mail.search([("model", "=", "sale.order"), ("res_id", "in", (due | later).ids)])
        # What the automation scheduler does, without its commits: the rule last ran 10 days ago.
        rule.last_run = fields.Datetime.now() - timedelta(days=10)
        rule = rule.with_context(__action_done={})
        for record in rule._search_time_based_automation_records(until=fields.Datetime.now()):
            rule._process(record)
        sent = Mail.search([("model", "=", "sale.order"), ("res_id", "in", (due | later).ids)]) - before
        self.assertEqual(sent.mapped("res_id"), [due.id], "only the layaway due within 3 days is reminded")

    def test_expiry(self):
        order = self._layaway(paid=200.0)
        sent = []
        with patch.object(LayawayOrder, "_xb_layaway_send", lambda rec, xmlid: sent.append(xmlid) or True):
            order.xb_layaway_deadline = self.today
            self.env["sale.order"]._xb_cron_layaways()
            self.assertFalse(sent, "the deadline day still counts")
            order.xb_layaway_deadline = self.today - timedelta(days=1)
            self.env["sale.order"]._xb_cron_layaways()
        self.assertEqual(order.xb_layaway_state, "expired")
        self.assertEqual(order.xb_layaway_fee_amount, 20.0)
        self.assertEqual(order.xb_layaway_refund_amount, 180.0)
        self.assertEqual(sent[-1], "xb_sale_order_from_pos.mail_template_layaway_expired")
        self.assertTrue(order.activity_ids, "the salesperson gets a to-do")

    def test_extend_reactivates(self):
        order = self._layaway(paid=200.0)
        order._xb_layaway_expire()
        self.assertTrue(order.xb_layaway_activity_id)
        wizard = self.env["xb.layaway.extend"].with_context(default_order_id=order.id).create({})
        self.assertGreater(wizard.deadline, self.today)
        wizard.action_confirm()
        self.assertEqual(order.xb_layaway_state, "active")
        self.assertFalse(order.xb_layaway_expired_on)
        self.assertFalse(order.activity_ids)

    def test_templates_render(self):
        order = self._layaway(paid=200.0)
        for xmlid in ("mail_template_layaway_reminder", "mail_template_layaway_expired"):
            template = self.env.ref("xb_sale_order_from_pos.%s" % xmlid)
            body = template._render_field("body_html", order.ids)[order.id]
            self.assertIn(order.name, body)

    def test_holds_for_the_register(self):
        config = self.env["pos.config"].create({"name": "Layaway register"})
        order = self._layaway(paid=100.0)
        holds = self.env["sale.order"].xb_pos_layaway_holds([self.product.id], config.id)
        self.assertEqual(holds[self.product.id]["held"], 1.0)
        self.assertEqual(holds[self.product.id]["holds"][0]["name"], order.name)
        order.xb_layaway_expired_on = self.today
        self.assertFalse(self.env["sale.order"].xb_pos_layaway_holds([self.product.id], config.id),
                         "an expired layaway stops holding the goods")
        self.company.xb_layaway_warn_reserved = False
        order.xb_layaway_expired_on = False
        self.assertFalse(self.env["sale.order"].xb_pos_layaway_holds([self.product.id], config.id))

    def test_order_minimum_down_payment(self):
        order = self._layaway(paid=0.0, xb_so_kind="order", xb_layaway_down_percent=30.0)
        self.assertTrue(order._xb_layaway_check_payment(200.0), "below the 30% down payment")
        self.assertFalse(order._xb_layaway_check_payment(300.0))
        self.assertFalse(order._xb_layaway_check_payment(1000.0), "the whole order is always fine")
        order.amount_unpaid = 700.0
        self.assertFalse(order._xb_layaway_check_payment(10.0), "after the down payment, any amount")
        self.assertTrue(order._xb_layaway_check_payment(701.0), "never more than the balance")
        self.assertEqual(order.xb_layaway_paid, 300.0)
        self.assertFalse(order.xb_layaway_state, "an order is not a layaway")

    def test_order_reminder_rule(self):
        rule = self.env.ref("xb_sale_order_from_pos.automation_order_reminder")
        due = self._layaway(paid=300.0, xb_so_kind="order", commitment_date=fields.Datetime.now() + timedelta(days=2))
        paid = self._layaway(paid=1000.0, xb_so_kind="order", commitment_date=fields.Datetime.now() + timedelta(days=2))
        Mail = self.env["mail.mail"].sudo()
        before = Mail.search([("model", "=", "sale.order"), ("res_id", "in", (due | paid).ids)])
        rule.last_run = fields.Datetime.now() - timedelta(days=10)
        rule = rule.with_context(__action_done={})
        for record in rule._search_time_based_automation_records(until=fields.Datetime.now()):
            rule._process(record)
        sent = Mail.search([("model", "=", "sale.order"), ("res_id", "in", (due | paid).ids)]) - before
        self.assertEqual(sent.mapped("res_id"), [due.id], "only an order with a balance is reminded")
        self.assertIn(due.name, sent.body_html)
