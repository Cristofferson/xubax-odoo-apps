# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged("post_install", "-at_install")
class TestXbSaleOrderFromPosTour(TestPointOfSaleHttpCommon):

    def test_xb_create_order_flows(self):
        """Tour: create Quotation / Order / Layaway from the POS cart button, then take
        the layaway's down payment from the list of orders."""
        # Enable the feature and its options on the test POS, and configure a
        # down-payment product so the Layaway (advance) flow passes the guard.
        # Odoo 17 hides the down-payment product from the register's product list, so
        # the test sells "Wall Shelf Unit" and takes advances with a product of its own.
        down_payment = self.env["product.product"].create({
            "name": "Down Payment (xb test)",
            "type": "service",
            "available_in_pos": False,
            "taxes_id": False,
        })
        self.main_pos_config.write({
            "xb_enable_sale_order": True,
            "xb_allow_quotation": True,
            "xb_differentiate_order_layaway": True,
            "xb_enrich_receipt": True,
            "down_payment_product_id": down_payment.id,
        })
        # Odoo 17's own list of orders (pos_sale) reads sale.order: the cashier needs
        # Sales rights, as in any shop that recovers orders at the register.
        self.pos_user.groups_id += self.env.ref("sales_team.group_sale_salesman")
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_tour("/pos/ui?config_id=%d" % self.main_pos_config.id, "XbCreateOrderFlows", login="pos_user")

        # Three sale orders were created for the customer. None is confirmed on
        # creation (all are sent quotations); the layaway is confirmed natively by
        # pos_sale when its down payment is paid at the register.
        orders = self.env["sale.order"].search([("partner_id", "=", self.partner_test_1.id)])
        self.assertEqual(len(orders), 3, "Expected 3 sale orders created from POS")
        by_kind = {order.xb_so_kind: order for order in orders}
        self.assertEqual(set(by_kind), {"quotation", "order", "layaway"})
        self.assertEqual(by_kind["quotation"].state, "sent")
        self.assertEqual(by_kind["order"].state, "sent")
        self.assertTrue(by_kind["order"].commitment_date, "the delivery date asked at the register is kept")
        layaway = by_kind["layaway"]
        self.assertEqual(layaway.state, "sale")
        self.assertEqual(layaway.xb_layaway_state, "active")
        self.assertAlmostEqual(layaway.amount_unpaid, 0.98)
        self.assertFalse(layaway.picking_ids, "a layaway from the register creates no delivery")
