# -*- coding: utf-8 -*-
import uuid

from odoo import Command, fields
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged("post_install", "-at_install")
class TestXbSaleOrderFromPosTour(TestPointOfSaleHttpCommon):

    def _xb_enable(self, **vals):
        self.main_pos_config.write({
            "xb_enable_sale_order": True,
            "xb_allow_quotation": True,
            "xb_differentiate_order_layaway": True,
            # Its own product: Odoo hides the down-payment product from the register's list.
            "down_payment_product_id": self.env["product.product"].create({
                "name": "Down payment", "type": "service", "available_in_pos": True,
                "taxes_id": [Command.clear()]}).id,
            **vals,
        })

    def test_xb_create_order_flows(self):
        """Tour: create Quotation / Order / Layaway from the POS cart button."""
        # Enable the feature and its options on the test POS, and configure a
        # down-payment product so the Layaway (advance) flow passes the guard.
        self._xb_enable(xb_autoprint_on_create=True, xb_enrich_receipt=True)
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour("XbCreateOrderFlows", login="pos_user")

        # Backend: three documents for the customer, none confirmed on creation (Odoo
        # confirms them natively when a payment is validated at the register).
        orders = self.env["sale.order"].search([("partner_id", "=", self.partner_test_1.id)])
        self.assertEqual(len(orders), 3, "Expected 3 sale orders created from POS")
        self.assertEqual(sorted(orders.mapped("xb_so_kind")), ["layaway", "order", "quotation"])
        self.assertEqual(set(orders.mapped("state")), {"sent"})
        by_kind = {order.xb_so_kind: order for order in orders}
        self.assertFalse(by_kind["quotation"].commitment_date, "a quotation commits to no date")
        self.assertTrue(by_kind["order"].commitment_date)
        self.assertTrue(by_kind["layaway"].xb_layaway_deadline)

    def _xb_pay_down_payment(self, sale_order, amount):
        """The paid register order of a down payment on SALE_ORDER, as the register syncs it."""
        self.main_pos_config.open_ui()
        session = self.main_pos_config.current_session_id
        product = self.main_pos_config.down_payment_product_id
        order_uuid = str(uuid.uuid4())
        data = {
            "amount_paid": amount, "amount_return": 0, "amount_tax": 0, "amount_total": amount,
            "company_id": self.env.company.id, "date_order": fields.Datetime.to_string(fields.Datetime.now()),
            "fiscal_position_id": False, "name": "Order %s" % order_uuid,
            "partner_id": sale_order.partner_id.id,
            "lines": [Command.create({
                "product_id": product.id, "qty": 1, "price_unit": amount, "discount": 0,
                "price_subtotal": amount, "price_subtotal_incl": amount, "tax_ids": [Command.clear()],
                "sale_order_origin_id": sale_order.id,
                "extra_tax_data": {"computation_key": "down_payment"},
            })],
            "payment_ids": [Command.create({
                "amount": amount, "name": fields.Datetime.now(),
                "payment_method_id": self.main_pos_config.payment_method_ids[0].id,
            })],
            "pricelist_id": self.main_pos_config.available_pricelist_ids[0].id,
            "session_id": session.id, "to_invoice": False, "user_id": self.env.uid, "uuid": order_uuid,
        }
        result = self.env["pos.order"].sync_from_ui([data])
        return self.env["pos.order"].search([("uuid", "=", order_uuid)]), result

    def test_xb_layaway_down_payment_and_receipt(self):
        """A layaway made from the register, its down payment paid at the register, and the
        receipt Odoo draws on the server (download, email) with the order's balance."""
        self._xb_enable(xb_enrich_receipt=True, xb_show_portal_link=True)
        self.env.company.write({"xb_layaway_days": 30, "xb_layaway_down_percent": 10.0})
        result = self.env["sale.order"].xb_create_order_from_pos({
            "pos_config_id": self.main_pos_config.id,
            "partner_id": self.partner_test_1.id,
            "type": "layaway",
            "with_down_payment": True,
            "lines": [{"product_id": self.env["product.product"].create({
                "name": "Ring", "type": "consu", "list_price": 500.0, "taxes_id": [Command.clear()],
                "available_in_pos": True}).id, "qty": 1, "price_unit": 500.0, "discount": 0, "tax_ids": []}],
            "amount_total": 500.0,
        })
        sale_order = self.env["sale.order"].browse(result["sale_order_id"])
        self.assertEqual(sale_order.state, "sent")
        self.assertEqual(result["layaway_down_payment"], 50.0)
        self.assertIn("/my/orders/%s" % sale_order.id, result["portal_url"])

        pos_order, synced = self._xb_pay_down_payment(sale_order, 100.0)
        self.assertEqual(sale_order.state, "sale", "Odoo confirms the layaway with its down payment")
        self.assertEqual(sale_order.amount_unpaid, 400.0)
        self.assertEqual(sale_order.xb_layaway_state, "active")
        self.assertFalse(sale_order.picking_ids, "an order made at the register makes no delivery")
        self.assertIn(sale_order.id, [so["id"] for so in synced.get("sale.order", [])],
                      "the register gets the fresh balance with the sync")

        data = pos_order._xb_receipt_sale_order_data()
        self.assertEqual(data["xb_so"]["kind"], "layaway")
        self.assertTrue(data["xb_so"]["portal_qr"])
        self.assertTrue(data["xb_hide_self_invoice_qr"])
        html = str(pos_order.order_receipt_generate_html())
        for text in ("LAYAWAY", sale_order.name, "Balance due", "Pay the balance by:", "Pay or review your order online:"):
            self.assertIn(text, html)
