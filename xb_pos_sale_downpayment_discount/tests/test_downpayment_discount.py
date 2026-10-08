# -*- coding: utf-8 -*-
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged("post_install", "-at_install")
class TestDownPaymentDiscount(TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        cls.down_payment = cls.env["product.product"].create({
            "name": "Down payment",
            "type": "service",
            "list_price": 1000.0,
            "taxes_id": [(6, 0, [])],
            "available_in_pos": True,
        })
        cls.config.down_payment_product_id = cls.down_payment
        cls.ring = cls.env["product.product"].create({
            "name": "Ring",
            "list_price": 3000.0,
            "taxes_id": [(6, 0, [])],
        })
        cls.partner = cls.env["res.partner"].create({"name": "Customer"})

    def _sale_order(self):
        # The order is made in Sales (the POS user of the test cannot create it).
        order = self.env["sale.order"].sudo().create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.ring.id,
                "product_uom_qty": 1,
                "price_unit": 3000.0,
                "tax_ids": [(6, 0, [])],
            })],
        })
        order.action_confirm()
        return order

    def _pay_down_payment(self, order, discount):
        self.open_new_session()
        # The POS sends the line total with its discount (the test helper only applies the
        # discount when the product has taxes, so the totals are given as the POS sends them).
        total = 1000.0 * (1 - discount / 100.0)
        data = self.create_ui_order_data([{
            "product": self.down_payment,
            "quantity": 1,
            "discount": discount,
            "price_subtotal": total,
            "price_subtotal_incl": total,
            "sale_order_origin_id": order.id,
        }], customer=self.partner)
        self.env["pos.order"].sync_from_ui([data])
        return data

    def test_discount_goes_to_the_order(self):
        """1,000 down payment with 10 %: the customer pays 900 and saved 100. The
        order gets a -100 discount line, so its balance is what is really owed."""
        order = self._sale_order()
        self._pay_down_payment(order, 10.0)
        discount = order.order_line.filtered("xb_pos_discount_line_id")
        self.assertEqual(len(discount), 1)
        self.assertAlmostEqual(discount.price_total, -100.0)
        self.assertAlmostEqual(order.amount_total, 2900.0)
        self.assertAlmostEqual(order.amount_unpaid, 2000.0)
        self.assertIn("10%", order.message_ids[:1].body)

    def test_no_discount_no_line(self):
        order = self._sale_order()
        self._pay_down_payment(order, 0.0)
        self.assertFalse(order.order_line.filtered("xb_pos_discount_line_id"))
        self.assertAlmostEqual(order.amount_unpaid, 2000.0)

    def test_synced_twice_carried_once(self):
        """The POS may send the same ticket again: the discount is added only once."""
        order = self._sale_order()
        data = self._pay_down_payment(order, 10.0)
        self.env["pos.order"].sync_from_ui([data])
        self.assertEqual(len(order.order_line.filtered("xb_pos_discount_line_id")), 1)
        self.assertAlmostEqual(order.amount_total, 2900.0)
