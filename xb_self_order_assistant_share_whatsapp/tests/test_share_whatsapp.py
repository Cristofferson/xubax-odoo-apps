# -*- coding: utf-8 -*-
import json
from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.pos_self_order.tests.self_order_common_test import SelfOrderCommonTest


@tagged("post_install", "-at_install")
class TestShareWhatsApp(SelfOrderCommonTest):

    def setUp(self):
        super().setUp()
        self.env.company.country_id = self.env.ref("base.mx")
        account = self.env["whatsapp.account"].create({
            "name": "Shop", "app_uid": "a", "app_secret": "b", "account_uid": "c",
            "phone_uid": "d", "token": "e", "allowed_company_ids": [(6, 0, self.env.company.ids)],
            "notify_user_ids": [(6, 0, [self.env.ref("base.user_admin").id])],
        })
        self.pos_config.write({
            "self_ordering_mode": "kiosk", "xb_va_enabled": True, "xb_va_name": "Ana",
            "self_ordering_default_user_id": self.pos_user.id,
            "xb_va_ho_user_ids": [(6, 0, [self.env.ref("base.user_admin").id])],
        })
        action = self.pos_config.action_xb_va_create_wa_template()
        self.template = self.env["whatsapp.template"].browse(action["res_id"])
        self.assertIn(self.env.company, self.template.wa_account_id.allowed_company_ids)
        self.assertTrue(account)
        self.assertEqual(self.template.model, "xb.va.conversation")
        self.assertEqual(len(self.template.variable_ids), 3)
        self.template.status = "approved"
        self.pos_config.xb_va_wa_send_template_id = self.template
        self.pos_config.with_user(self.pos_user).open_ui()
        self.product = self.cola.product_tmpl_id
        self.conv = self.env["xb.va.conversation"].create({
            "config_id": self.pos_config.id,
            "transcript": "Cliente: Quiero algo sin azúcar\nAna: Te muestro la Coca-Cola.\n",
            "product_ids": [(6, 0, self.product.ids)],
        })

    def _fake_send(self, *args, **kwargs):
        return self.env["whatsapp.message"].sudo().new({"state": "outgoing"})

    def test_channel_offered_only_with_approved_template(self):
        self.assertIn("whatsapp", self.pos_config._xb_va_settings()["share"])
        names = [t["name"] for t in self.conv._xb_va_tools()]
        self.assertIn("enviar_seleccion", names)
        self.template.status = "pending"
        self.assertNotIn("whatsapp", self.pos_config._xb_va_settings()["share"])

    def test_send_selection(self):
        """The customer is found or created, the page exists, the conversation is kept and a lead is born."""
        with patch.object(type(self.env["whatsapp.composer"]), "_send_whatsapp_template", self._fake_send):
            self.conv._xb_va_share("whatsapp", "443 123 4567")
        self.assertTrue(self.conv.shared)
        self.assertTrue(self.conv.partner_id)
        self.assertEqual(self.conv.phone, "+524431234567", "Sent in international format")
        self.assertTrue(self.conv.share_url.endswith("/xb-va/s/%s" % self.conv.share_token))
        self.assertIn("Coca-Cola", self.conv.partner_id.message_ids[:1].body)
        lead = self.env["crm.lead"].search([("partner_id", "=", self.conv.partner_id.id)])
        self.assertEqual(len(lead), 1)
        # Same number written differently: same customer.
        conv2 = self.env["xb.va.conversation"].create({"config_id": self.pos_config.id})
        with patch.object(type(self.env["whatsapp.composer"]), "_send_whatsapp_template", self._fake_send):
            conv2._xb_va_share("whatsapp", "+52 (443) 123-4567")
        self.assertEqual(conv2.partner_id, self.conv.partner_id)

    def test_selection_page(self):
        self.conv._xb_va_ensure_share()
        page = self.url_open("/xb-va/s/%s" % self.conv.share_token)
        self.assertEqual(page.status_code, 200)
        self.assertIn("Te muestro la Coca-Cola", page.text)
        self.assertIn(self.product.name, page.text)
        image = self.url_open("/xb-va/s/%s/img/%s" % (self.conv.share_token, self.product.id))
        self.assertEqual(image.status_code, 200)
        self.assertEqual(self.url_open("/xb-va/s/%s" % ("x" * 32)).status_code, 404)

    def test_share_route_checks_the_number(self):
        body = self.url_open("/xb-va/%s/share" % self.pos_config.id, data=json.dumps({
            "jsonrpc": "2.0", "method": "call", "params": {
                "access_token": self.pos_config.access_token, "token": self.conv.token,
                "channel": "whatsapp", "phone": "123"}}), headers={"Content-Type": "application/json"}).json()
        self.assertFalse(body["result"]["ok"])
