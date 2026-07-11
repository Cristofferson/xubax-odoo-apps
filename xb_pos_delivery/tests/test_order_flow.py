# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from ..drivers.uber_eats import UberEatsDriver
from .common import XbDeliveryCommon


@tagged('post_install', '-at_install')
class TestOrderFlow(XbDeliveryCommon):

    def setUp(self):
        super().setUp()
        self.open_new_session()

    def test_incoming_order_totals(self):
        order = self.account_uber._process_incoming_order(self._norm_order())
        self.assertEqual(order.state, 'draft')
        self.assertEqual(order.xb_delivery_status, 'placed')
        self.assertEqual(order.session_id, self.pos_session)
        # 3 tacos @100 + 1 agua @35 = 335.00 tax included
        self.assertAlmostEqual(order.amount_total, 335.0, places=2)
        # IVA 16% included: base = 335 / 1.16
        self.assertAlmostEqual(order.amount_tax, 335.0 - 335.0 / 1.16, places=1)
        self.assertEqual(order.partner_id.name, 'Juan Prueba')
        self.assertEqual(len(order.lines), 2)
        taco_line = order.lines.filtered(
            lambda l: l.product_id.product_tmpl_id == self.taco)
        self.assertEqual(taco_line.qty, 3)
        self.assertTrue(taco_line.attribute_value_ids)

    def test_duplicate_webhook_is_idempotent(self):
        order1 = self.account_uber._process_incoming_order(self._norm_order())
        order2 = self.account_uber._process_incoming_order(self._norm_order())
        self.assertEqual(order1, order2)

    def test_accept_ready_payment_cycle(self):
        order = self.account_uber._process_incoming_order(self._norm_order())
        with patch.object(UberEatsDriver, 'accept_order', return_value=True):
            order.action_xb_accept()
        self.assertEqual(order.xb_delivery_status, 'accepted')
        with patch.object(UberEatsDriver, 'mark_ready', return_value=True):
            order.action_xb_ready()
        self.assertEqual(order.xb_delivery_status, 'ready')
        self.assertEqual(order.state, 'paid')
        self.assertEqual(
            order.payment_ids.payment_method_id,
            self.account_uber.payment_method_id)
        self.assertAlmostEqual(order.payment_ids.amount, 335.0, places=2)

    def test_auto_accept(self):
        self.account_uber.auto_accept = True
        with patch.object(UberEatsDriver, 'accept_order', return_value=True):
            order = self.account_uber._process_incoming_order(self._norm_order())
        self.assertEqual(order.xb_delivery_status, 'accepted')

    def test_reject(self):
        order = self.account_uber._process_incoming_order(self._norm_order())
        with patch.object(UberEatsDriver, 'deny_order', return_value=True):
            order.action_xb_reject('Muy ocupados')
        self.assertEqual(order.xb_delivery_status, 'cancelled')
        self.assertEqual(order.state, 'cancel')

    def test_platform_cancel_after_payment_warns(self):
        order = self.account_uber._process_incoming_order(self._norm_order())
        with patch.object(UberEatsDriver, 'accept_order', return_value=True), \
                patch.object(UberEatsDriver, 'mark_ready', return_value=True):
            order.action_xb_accept()
            order.action_xb_ready()
        order._xb_cancel_locally()
        self.assertEqual(order.xb_delivery_status, 'cancelled')
        # Paid order is not silently flipped to cancel
        self.assertEqual(order.state, 'paid')

    def test_delivery_order_cannot_be_deleted(self):
        order = self.account_uber._process_incoming_order(self._norm_order())
        with self.assertRaises(UserError):
            order.unlink()

    def test_cash_pickup_paid_in_cash(self):
        norm = self._norm_order(external_id='ORD-CASH', type='pickup',
                                cash_due=335.0)
        order = self.account_uber._process_incoming_order(norm)
        with patch.object(UberEatsDriver, 'accept_order', return_value=True), \
                patch.object(UberEatsDriver, 'mark_ready', return_value=True):
            order.action_xb_accept()
            order.action_xb_ready()
        self.assertEqual(order.state, 'paid')
        self.assertEqual(order.payment_ids.payment_method_id.type, 'cash')

    def test_restaurant_funded_discount_line(self):
        norm = self._norm_order(external_id='ORD-DISC', discounts=[{
            'title': 'Promo 2x1', 'code': 'PROMO', 'amount': 50.0,
            'restaurant_funded': True,
        }])
        order = self.account_uber._process_incoming_order(norm)
        self.assertAlmostEqual(order.amount_total, 285.0, places=2)

    def test_tax_excluded_product_not_double_taxed(self):
        """Platform prices are tax inclusive: with a price-EXCLUDED tax on
        the product, the tax must be deflated, not added on top."""
        tax_excl = self.env['account.tax'].create({
            'name': 'IVA 16% excl',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'company_id': self.company.id,
        })
        torta = self.env['product.template'].create({
            'name': 'Torta', 'type': 'consu', 'available_in_pos': True,
            'list_price': 100.0, 'taxes_id': [(6, 0, tax_excl.ids)],
        })
        norm = self._norm_order(external_id='ORD-EXCL', items=[{
            'ref': str(torta.id), 'name': 'Torta', 'qty': 1,
            'unit_price': 116.0, 'options': [], 'note': '',
        }])
        order = self.account_uber._process_incoming_order(norm)
        # The customer paid 116 on the platform: total must be 116, not 134.56
        self.assertAlmostEqual(order.amount_total, 116.0, places=2)
        self.assertAlmostEqual(order.lines.price_subtotal, 100.0, places=2)

    def test_no_session_raises(self):
        self.pos_session.post_closing_cash_details(0)
        self.pos_session.close_session_from_ui()
        with self.assertRaises(UserError):
            self.account_uber._process_incoming_order(
                self._norm_order(external_id='ORD-CLOSED'))

    def test_wizard_test_order(self):
        wizard = self.env['xb.delivery.test.order'].create({
            'account_id': self.account_uber.id,
            'product_ids': [(6, 0, self.agua.ids)],
        })
        action = wizard.action_create_test_order()
        order = self.env['pos.order'].browse(action['res_id'])
        self.assertTrue(order.xb_delivery_identifier.startswith('TEST-'))
        self.assertAlmostEqual(order.amount_total, 35.0, places=2)
