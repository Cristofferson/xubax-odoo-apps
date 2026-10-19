# -*- coding: utf-8 -*-
import base64
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged

from odoo.addons.whatsapp.tests.common import WhatsAppCommon
from odoo.addons.xb_business_agent.models.discuss_channel import DiscussChannel

# Smallest valid PDF: enough for the history to send it as a document block.
PDF = (b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
       b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 10 10]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF")


def _usage():
    return SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=0, cache_creation_input_tokens=0)


def _text(texto):
    return SimpleNamespace(stop_reason="end_turn", usage=_usage(),
                           content=[SimpleNamespace(type="text", text=texto)])


def _tool(nombre, entrada, uid="tu_1"):
    return SimpleNamespace(stop_reason="tool_use", usage=_usage(),
                           content=[SimpleNamespace(type="tool_use", id=uid, name=nombre, input=entrada)])


class FakeClient:
    """Anthropic client that returns the scripted answers and keeps the requests."""

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.peticiones = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.peticiones.append(kwargs)
        return self.respuestas.pop(0)


@tagged("post_install", "-at_install")
class TestBusinessAgent(WhatsAppCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff = cls.user_wa_admin
        cls.tipo = cls.env["appointment.type"].create({
            "name": "Consultation",
            "appointment_duration": 1.0,
            "appointment_tz": "UTC",
            "schedule_based_on": "users",
            "staff_user_ids": [(6, 0, cls.staff.ids)],
            "min_schedule_hours": 0,
            "max_schedule_days": 15,
            "slot_ids": [(0, 0, {"weekday": str(d), "start_hour": 9.0, "end_hour": 17.0}) for d in range(1, 8)],
        })
        cls.env["xb.business.knowledge"].create({"kind": "price", "name": "Prices", "content": "Consultation: 50 USD."})
        cls.account = cls.whatsapp_account
        cls.account.sudo().write({
            "xb_ba_enabled": True,
            "xb_ba_shadow": True,
            "xb_ba_api_key": "test-key",
            "xb_ba_user_ids": [(6, 0, cls.staff.ids)],
            "xb_ba_appointment_type_ids": [(6, 0, cls.tipo.ids)],
            "xb_ba_company_name": "Test Clinic",
        })
        cls.number = "+32499123456"

    def _inbound(self, body="", attachments=None):
        channel = self.account._find_active_channel(self.number, sender_name="Ana", create_if_not_found=True)
        kwargs = {"message_type": "whatsapp_message", "author_id": channel.whatsapp_partner_id.id,
                  "subtype_xmlid": "mail.mt_comment",
                  "whatsapp_inbound_msg_uid": f"wamid.test.{fields.Datetime.now().timestamp()}.{len(channel.message_ids)}"}
        if body:
            kwargs["body"] = body
        if attachments:
            kwargs["attachments"] = attachments
        channel.message_post(**kwargs)
        return channel, self.env["xb.business.job"].search([("channel_id", "=", channel.id)], limit=1)

    def _answer(self, channel, job, respuestas):
        client = FakeClient(respuestas)
        with patch.object(DiscussChannel, "_xb_ba_client", return_value=client):
            channel._xb_ba_answer(job)
        return client

    def test_rehearsal_reply_is_a_note(self):
        channel, job = self._inbound("Hi, how much is a consultation?")
        self.assertEqual(job.state, "pending", "An inbound message queues a job")
        client = self._answer(channel, job, [_text("A consultation is *50 USD*.")])
        self.assertEqual(job.state, "draft")
        self.assertIn("50 USD", client.peticiones[0]["system"][0]["text"], "The knowledge base is in the prompt")
        nota = channel.message_ids.filtered(lambda m: m.message_type == "comment")[:1]
        self.assertIn("50 USD", nota.body)
        self.assertFalse(channel.message_ids.wa_message_ids.filtered(lambda w: w.message_type == "outbound"),
                         "Rehearsal mode sends nothing")
        # The rehearsal note is read back as the agent's own turn.
        historial = channel._xb_ba_history()
        self.assertEqual([t["role"] for t in historial], ["user", "assistant"])

    def test_live_reply_is_sent(self):
        self.account.xb_ba_shadow = False
        channel, job = self._inbound("Hello")
        with self.mockWhatsappGateway():
            self._answer(channel, job, [_text("Hello! How can I help?")])
        self.assertEqual(job.state, "done")
        self.assertEqual(len(self._wa_msg_sent), 1)

    def test_register_lead(self):
        channel, job = self._inbound("I want a consultation, I'm Ana Pérez")
        self._answer(channel, job, [
            _tool("register_lead", {"name": "Ana Pérez", "service": "Consultation", "email": "",
                                    "city": "", "notes": "Wants a consultation"}),
            _text("Thanks, Ana!"),
        ])
        lead = channel.xb_ba_lead_id
        self.assertTrue(lead)
        self.assertEqual(lead.contact_name, "Ana Pérez")
        self.assertEqual(lead.partner_id, channel.whatsapp_partner_id)
        self.assertEqual(lead.user_id, self.staff)
        self.assertIn("register_lead", job.log)

    def test_book_and_cancel(self):
        channel, job = self._inbound("Can I book?")
        slots = channel._xb_ba_tool_list_slots(job, {"appointment_type_id": self.tipo.id, "from_date": ""})
        self.assertTrue(slots["slots"], "There are free slots")
        inicio = slots["slots"][0].split(" ", 1)[1]  # «Monday 2026-10-19 09:00» → «2026-10-19 09:00»
        res = channel._xb_ba_tool_book_appointment(job, {"appointment_type_id": self.tipo.id, "start": inicio,
                                                         "name": "Ana Pérez", "email": "ana@example.com"})
        self.assertTrue(res["ok"], res)
        evento = self.env["calendar.event"].browse(res["appointment_id"])
        self.assertEqual(evento.appointment_type_id, self.tipo)
        self.assertIn(channel.whatsapp_partner_id, evento.partner_ids)
        # The same slot is no longer offered.
        again = channel._xb_ba_tool_book_appointment(job, {"appointment_type_id": self.tipo.id, "start": inicio,
                                                           "name": "Other", "email": ""})
        self.assertFalse(again["ok"])
        mias = channel._xb_ba_tool_my_appointments(job, {})
        self.assertEqual([c["appointment_id"] for c in mias["appointments"]], [evento.id])
        self.assertTrue(channel._xb_ba_tool_cancel_appointment(job, {"appointment_id": evento.id})["ok"])
        self.assertFalse(evento.active)

    def test_only_allowed_types_and_own_appointments(self):
        otro_tipo = self.tipo.copy({"name": "Not allowed"})
        channel, job = self._inbound("Hi")
        res = channel._xb_ba_tool_list_slots(job, {"appointment_type_id": otro_tipo.id, "from_date": ""})
        self.assertFalse(res["ok"])
        ajena = self.env["calendar.event"].create({
            "name": "Someone else", "appointment_type_id": self.tipo.id, "user_id": self.staff.id,
            "start": fields.Datetime.now() + timedelta(days=2), "stop": fields.Datetime.now() + timedelta(days=2, hours=1)})
        self.assertFalse(channel._xb_ba_tool_cancel_appointment(job, {"appointment_id": ajena.id})["ok"])
        self.assertTrue(ajena.active)

    def test_human_reply_pauses_and_resume_word(self):
        channel, job = self._inbound("Hello")
        with self.mockWhatsappGateway():
            channel.with_user(self.staff).message_post(body="Hi Ana, it's Wasin", message_type="whatsapp_message")
        self.assertTrue(channel.xb_ba_paused_until)
        self.assertEqual(channel.xb_ba_pause_reason, "human")
        channel, job = self._inbound("Are you there?")
        self._answer(channel, job, [])
        self.assertIn(job.state, ("skipped", "draft"), "Paused: the model is not called")
        nota = channel.with_user(self.staff).message_post(body="#agente", message_type="whatsapp_message")
        self.assertEqual(nota.message_type, "comment", "#agente is a note, never sent to the customer")
        self.assertFalse(channel.xb_ba_paused_until)

    def test_pdf_goes_to_the_model(self):
        channel, job = self._inbound("Here is my receipt", attachments=[("receipt.pdf", PDF, {})])
        client = self._answer(channel, job, [_text("Thanks, I received it.")])
        bloques = client.peticiones[0]["messages"][0]["content"]
        documento = [b for b in bloques if b["type"] == "document"]
        self.assertEqual(len(documento), 1)
        self.assertEqual(base64.b64decode(documento[0]["source"]["data"]), PDF)

    def test_hand_over_notifies_team(self):
        channel, job = self._inbound("I want a refund")
        self._answer(channel, job, [
            _tool("hand_over", {"reason": "payments_or_complaints", "summary": "Wants a refund", "urgent": False}),
            _text("I've let the team know."),
        ])
        self.assertEqual(channel.xb_ba_pause_reason, "handoff")
        self.assertTrue(job.activity_ids.filtered(lambda a: a.user_id == self.staff))

    def test_disabled_or_not_allowed_number_does_nothing(self):
        self.account.xb_ba_only_numbers = "+1 555 000 0000"
        channel, job = self._inbound("Hello")
        self.assertFalse(job, "A number outside the test list is ignored")
