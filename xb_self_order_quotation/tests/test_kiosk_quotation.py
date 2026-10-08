# -*- coding: utf-8 -*-
import json

from odoo.tests import tagged

from odoo.addons.pos_self_order.tests.self_order_common_test import SelfOrderCommonTest


@tagged("post_install", "-at_install")
class TestKioskQuotation(SelfOrderCommonTest):

    def setUp(self):
        super().setUp()
        self.env.company.country_id = self.env.ref("base.mx")
        self.pos_config.write({
            "self_ordering_mode": "kiosk",
            "xb_kiosk_quotation": True,
            "other_devices": True,
            "epson_printer_ip": "192.168.0.10",
        })
        self.pos_config.with_user(self.pos_user).open_ui()

    def _quote(self, **params):
        values = {
            "access_token": self.pos_config.access_token,
            "name": "Ana López",
            "phone": "443 123 4567",
            "lines": [{"template_id": self.cola.product_tmpl_id.id, "ptav_ids": [], "qty": 2}],
            "send_whatsapp": False,
        }
        values.update(params)
        response = self.url_open(
            "/xb_kiosk/quotation",
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": values}),
            headers={"Content-Type": "application/json"},
        )
        body = response.json()
        self.assertIn("result", body, body.get("error"))
        return body["result"]

    def test_quotation_like_the_pos(self):
        """The kiosk cart becomes a quotation made like the POS ones."""
        result = self._quote()
        self.assertTrue(result.get("ok"), result)
        order = self.env["sale.order"].search([("name", "=", result["name"])])
        self.assertEqual(order.state, "sent")
        self.assertEqual(order.xb_so_kind, "quotation")
        self.assertEqual(order.origin, self.pos_config.name)
        self.assertFalse(order.user_id, "Nobody sold it yet")
        self.assertTrue(order.validity_date)
        self.assertAlmostEqual(order.amount_untaxed, 4.4)  # 2 × 2.20, taxes of the test company apart
        self.assertEqual(order.partner_id.phone_sanitized, "+524431234567")
        # The ticket image is drawn by wkhtmltoimage, which Odoo switches off in tests:
        # the quotation is saved anyway.
        self.assertIn("image", result)

    def test_customer_found_by_mobile(self):
        """The same mobile, written differently, is the same customer."""
        first = self._quote()
        second = self._quote(name="Ana", phone="+52 (443) 123-4567")
        orders = self.env["sale.order"].search([("name", "in", [first["name"], second["name"]])])
        self.assertEqual(len(orders), 2)
        self.assertEqual(len(orders.partner_id), 1)

    def test_invalid_mobile(self):
        before = self.env["sale.order"].search_count([])
        result = self._quote(phone="123")
        self.assertTrue(result.get("error"))
        self.assertEqual(self.env["sale.order"].search_count([]), before)

    def test_switched_off(self):
        self.pos_config.xb_kiosk_quotation = False
        result = self._quote()
        self.assertTrue(result.get("error"))
