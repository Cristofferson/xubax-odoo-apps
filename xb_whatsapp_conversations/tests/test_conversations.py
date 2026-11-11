# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import tagged, TransactionCase
from odoo.tools.safe_eval import safe_eval


@tagged("post_install", "-at_install")
class TestWhatsAppConversations(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Automated actions of the database (e.g. AI on new contacts) are not part of this test.
        if "base.automation" in cls.env:
            cls.env["base.automation"].search([]).active = False
        cls.customer = cls.env["res.partner"].create({"name": "Ana Cliente", "phone": "+52 55 5555 0001"})
        cls.chat = cls.env["discuss.channel"].create({
            "name": "Ana Cliente",
            "channel_type": "whatsapp",
            "whatsapp_number": "525555550001",
            "whatsapp_partner_id": cls.customer.id,
        })

    def _customer_writes(self, text):
        return self.chat.message_post(
            body=text, author_id=self.customer.id, message_type="whatsapp_message",
            whatsapp_inbound_msg_uid="wamid.%s" % text)

    def test_customer_message_awaits_reply_and_answer_clears_it(self):
        self.assertFalse(self.chat.xb_wac_last_dt)
        self._customer_writes("Hola")
        self.assertTrue(self.chat.xb_wac_last_dt)
        self.assertTrue(self.chat.xb_wac_waiting)
        self.assertEqual(self.chat.xb_wac_last_text, "Hola")
        with patch.object(type(self.env["whatsapp.message"]), "_send_message", lambda self, *a, **k: None):
            self.chat.message_post(body="Con gusto", message_type="whatsapp_message")
        self.assertFalse(self.chat.xb_wac_waiting)
        self.chat.invalidate_recordset(["xb_wac_last_text"])
        self.assertEqual(self.chat.xb_wac_last_text, "Con gusto")

    def test_internal_note_does_not_change_the_row(self):
        self._customer_writes("Precio?")
        when = self.chat.xb_wac_last_dt
        self.chat.message_post(body="nota interna", message_type="comment")
        self.assertEqual(self.chat.xb_wac_last_dt, when)
        self.assertTrue(self.chat.xb_wac_waiting)

    def test_refresh_from_history(self):
        self._customer_writes("Sigue disponible?")
        self.chat.write({"xb_wac_last_dt": False, "xb_wac_waiting": False})
        self.chat._xb_wac_refresh()
        self.assertTrue(self.chat.xb_wac_last_dt)
        self.assertTrue(self.chat.xb_wac_waiting)

    def test_menu_and_open_action(self):
        self._customer_writes("Hola")
        action = self.env.ref("xb_whatsapp_conversations.action_xb_wac_conversations")
        found = self.env["discuss.channel"].search(safe_eval(action.domain))
        self.assertIn(self.chat, found)
        self.assertIn("mail.action_discuss", self.chat.action_xb_wac_open()["url"])
        messages_menu = self.env.ref("whatsapp.whatsapp_message_menu")
        self.assertEqual(messages_menu.parent_id, self.env.ref("xb_whatsapp_conversations.menu_xb_wac_reports"))
