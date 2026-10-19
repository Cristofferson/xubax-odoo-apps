# -*- coding: utf-8 -*-
from odoo.tests import tagged

from odoo.addons.whatsapp.tests.common import WhatsAppCommon


@tagged("post_install", "-at_install")
class TestSellerAndAgent(WhatsAppCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = cls.whatsapp_account
        cls.account.sudo().write({"xb_ba_enabled": True, "xb_ba_api_key": "test-key"})
        cls.env["xb.business.knowledge"].create({"kind": "policy", "name": "Delivery",
                                                 "content": "Free delivery in 5 days."})
        cls.kiosk = cls.env["pos.config"].create({"name": "Kiosk",
                                                  "xb_va_enabled": True, "xb_va_knowledge": "We engrave for free."})

    def test_knowledge_from_the_agent(self):
        """The seller can know only its own text, the agent's knowledge base, or both."""
        self.assertIn("engrave", self.kiosk._xb_va_knowledge_text())
        self.assertNotIn("Free delivery", self.kiosk._xb_va_knowledge_text())
        self.kiosk.write({"xb_va_ba_kb_source": "agent", "xb_va_ba_account_id": self.account.id})
        text = self.kiosk._xb_va_knowledge_text()
        self.assertIn("Free delivery", text)
        self.assertNotIn("engrave", text)
        self.kiosk.xb_va_ba_kb_source = "both"
        text = self.kiosk._xb_va_knowledge_text()
        self.assertIn("Free delivery", text)
        self.assertIn("engrave", text)

    def test_agent_continues_the_kiosk_conversation(self):
        """A customer who talked at the kiosk writes on WhatsApp: the agent gets that conversation."""
        number = "+5214435550199"
        self.env["xb.va.conversation"].create({
            "config_id": self.kiosk.id, "phone": "443 555 0199",
            "transcript": "Customer: I need a desk for my home office.\nSofía: The Corner Desk is $85.",
        })
        channel = self.account._find_active_channel(number, sender_name="Ana", create_if_not_found=True)
        context = channel._xb_ba_context_text()
        self.assertIn("kiosk virtual seller", context)
        self.assertIn("Corner Desk is $85", context)
        other = self.account._find_active_channel("+5214435550100", sender_name="Bob", create_if_not_found=True)
        self.assertNotIn("kiosk virtual seller", other._xb_ba_context_text())
