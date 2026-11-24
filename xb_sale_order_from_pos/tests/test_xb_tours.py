# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged("post_install", "-at_install")
class TestXbSaleOrderFromPosTour(TestPointOfSaleHttpCommon):

    def test_xb_create_order_flows(self):
        """Tour: create Quotation / Order / Layaway from the POS cart button."""
        # Enable the feature and all sub-options on the test POS, and configure a
        # down-payment product so the Layaway (advance) flow passes the guard.
        # Odoo 18 hides the down-payment product from the product list (it is a POS
        # special product), so the tour sells the shelf and advances with a service.
        down_payment = self.env["product.product"].create({
            "name": "XB Down Payment", "type": "service", "available_in_pos": True,
            "taxes_id": [(5, 0, 0)],
        })
        self.main_pos_config.write({
            "xb_enable_sale_order": True,
            "xb_allow_quotation": True,
            "xb_differentiate_order_layaway": True,
            "down_payment_product_id": down_payment.id,
        })
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour("XbCreateOrderFlows", login="pos_user")

        # Backend assertion: three sale orders were created for the customer, one of
        # each kind. Nothing is confirmed on creation: all three are sent quotations
        # until a payment is collected (Odoo confirms them natively then).
        orders = self.env["sale.order"].search([
            ("partner_id", "=", self.partner_test_1.id),
        ])
        self.assertEqual(len(orders), 3, "Expected 3 sale orders created from POS")
        self.assertEqual(sorted(orders.mapped("xb_so_kind")), ["layaway", "order", "quotation"])
        self.assertEqual(orders.mapped("state"), ["sent"] * 3, "Nothing is confirmed on creation")
