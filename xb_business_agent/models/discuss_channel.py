# -*- coding: utf-8 -*-
"""The agent: listens to the WhatsApp conversation, thinks with Claude and answers.

What does NOT depend on the prompt:
* The appointments it can see or cancel are only those of THIS chat's contact.
* It only books the appointment types the business gave it on the account.
* If a person from the team replies, the agent goes quiet (pause).
"""
import base64
import io
import json
import logging
from datetime import datetime, timedelta

import pytz
import requests
from PIL import Image, ImageOps
from markupsafe import Markup

from odoo import api, fields, models, tools
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

XB_HISTORY_HOURS = 72
XB_HISTORY_LIMIT = 40
# Every how many hours the team is reminded when the customer insists during a pause.
XB_HOLD_HOURS = 2
# What a person types in the chat to hand the conversation back to the agent.
XB_RESUME_WORDS = {"#agente", "#bot", "#agent"}
# Marks the agent's rehearsal notes so they are read back as its own replies.
XB_DRAFT_MARK = "xb-agent-draft"
XB_MAX_TOOL_ROUNDS = 10
XB_VOICE_MARK = "[transcript] "
XB_VOICE_MODEL = "gpt-4o-mini-transcribe"
XB_VOICE_MAX_BYTES = 8 * 1024 * 1024
XB_VISION_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif")
XB_VISION_MAX = 3
XB_VISION_SIDE = 1568
# PDFs the agent can read: the most recent ones the customer sent.
XB_PDF_MAX = 2
XB_PDF_MAX_BYTES = 10 * 1024 * 1024
XB_FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _tool(name, description, properties):
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
    }


XB_TOOLS = [
    _tool("register_lead",
          "Registers (or updates) the person as an opportunity in the business CRM, with what they are interested in. "
          "Use it when they show real interest. If they were already registered, it updates their data.",
          {"name": {"type": "string", "description": "Person's name; empty if they didn't say."},
           "service": {"type": "string", "description": "Service they are interested in; empty if not known yet."},
           "email": {"type": "string", "description": "Email if given; empty otherwise."},
           "city": {"type": "string", "description": "City if given; empty otherwise."},
           "notes": {"type": "string", "description": "What matters from what they said (for whoever follows up), brief."}}),
    _tool("list_slots",
          "Free slots of an appointment type (from the list «Appointments you can book»). Returns up to 8 spread-out options.",
          {"appointment_type_id": {"type": "integer"},
           "from_date": {"type": "string", "description": "YYYY-MM-DD date to search from; empty = from today."}}),
    _tool("book_appointment",
          "Books an appointment in the Appointments app at a slot returned by list_slots. Confirm the day and time with the person first.",
          {"appointment_type_id": {"type": "integer"},
           "start": {"type": "string", "description": "YYYY-MM-DD HH:MM in the appointment's local time."},
           "name": {"type": "string", "description": "Full name of who will attend."},
           "email": {"type": "string", "description": "Email to send the confirmation to; empty if not given."}}),
    _tool("my_appointments",
          "Upcoming appointments of the person in this chat (to confirm, change or cancel).",
          {}),
    _tool("cancel_appointment",
          "Cancels an upcoming appointment of the person in this chat (id from my_appointments). Ask for confirmation first.",
          {"appointment_id": {"type": "integer"}}),
    _tool("hand_over",
          "Notifies a person from the team so they reply. You can keep chatting; tell the person the team was notified.",
          {"reason": {"type": "string", "enum": ["unknown", "asks_for_person", "payments_or_complaints", "sensitive", "other"]},
           "summary": {"type": "string", "description": "What the person needs, in 1 to 3 lines."},
           "urgent": {"type": "boolean"}}),
]


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    xb_ba_paused_until = fields.Datetime("Agent paused until", copy=False)
    xb_ba_pause_reason = fields.Selection([
        ("human", "A person replied"),
        ("handoff", "The agent handed it over"),
    ], string="Pause reason", copy=False)
    xb_ba_hold_dt = fields.Datetime("Last reminder while paused", copy=False)
    xb_ba_lead_id = fields.Many2one("crm.lead", string="Opportunity", copy=False)

    # ------------------------------------------------------------------
    # Incoming
    # ------------------------------------------------------------------
    def message_post(self, *args, body="", message_type="notification", **kwargs):
        # «#agente» typed by someone from the team: it is not sent to the
        # customer, it only hands the chat back to the agent.
        if (self.channel_type == "whatsapp" and message_type == "whatsapp_message"
                and not kwargs.get("whatsapp_inbound_msg_uid")
                and self.env.user._is_internal()
                and html2plaintext(body or "").strip().lower() in XB_RESUME_WORDS):
            # Return a NEW message (the note): returning one already on screen
            # makes Discuss render it twice and crash.
            return self._xb_ba_resume_note()
        return super().message_post(*args, body=body, message_type=message_type, **kwargs)

    def _xb_ba_resume_note(self):
        self.ensure_one()
        channel = self.sudo()
        if channel.xb_ba_paused_until:
            channel.write({"xb_ba_paused_until": False, "xb_ba_pause_reason": False, "xb_ba_hold_dt": False})
            texto = self.env._("%s handed the chat back to the agent.", self.env.user.name)
        else:
            texto = self.env._("The chat was already with the agent.")
        return channel.message_post(
            body=Markup("<p>↩️ %s</p>") % texto,
            message_type="comment", subtype_xmlid="mail.mt_note",
            author_id=self.env.user.partner_id.id)

    def _notify_thread(self, message, msg_vals=False, **kwargs):
        res = super()._notify_thread(message, msg_vals=msg_vals, **kwargs)
        for channel in self:
            if channel.channel_type != "whatsapp":
                continue
            acc = channel.wa_account_id.sudo()
            if not acc.xb_ba_enabled or not acc._xb_ba_allows(channel.whatsapp_number):
                continue
            try:
                if kwargs.get("whatsapp_inbound_msg_uid"):
                    self.env["xb.business.job"]._xb_enqueue(channel, message)
                elif channel._xb_ba_is_human_reply(message):
                    channel.sudo().write({
                        "xb_ba_paused_until": fields.Datetime.now() + timedelta(hours=max(acc.xb_ba_pause_hours, 0)),
                        "xb_ba_pause_reason": "human",
                    })
            except Exception:  # noqa: BLE001 - never break reception
                _logger.exception("xb_business_agent: could not queue message %s", message.id)
        return res

    def _xb_ba_is_human_reply(self, message):
        """A person from the team replied on WhatsApp from Odoo."""
        if message.message_type != "whatsapp_message":
            return False
        if message.author_id == self.env.ref("base.partner_root"):
            return False
        return bool(message.author_id.user_ids.filtered(lambda u: not u.share))

    # ------------------------------------------------------------------
    # What the agent reads
    # ------------------------------------------------------------------
    def _xb_ba_tz(self):
        return pytz.timezone(self.env.company.partner_id.tz or self.env.user.tz or "UTC")

    def _xb_ba_context_text(self):
        ahora = datetime.now(self._xb_ba_tz())
        partner = self.whatsapp_partner_id.sudo()
        lineas = [f"Context (written by the system, not by the customer). Local date and time: {ahora:%A %Y-%m-%d %H:%M}.",
                  f"Person's WhatsApp: {self.whatsapp_number}."]
        if partner and partner.name and partner.name != self.whatsapp_number:
            lineas.append(f"Name in the contacts: {partner.name}.")
        lead = self.xb_ba_lead_id.sudo()
        if lead:
            lineas.append(f"Already registered as a lead: «{lead.name}» (stage {lead.stage_id.name}).")
        citas = self._xb_ba_my_events()
        if citas:
            lineas.append("Upcoming appointments: " + "; ".join(
                f"{e.name} on {self._xb_ba_fmt(e.start)}" for e in citas))
        if self.xb_ba_pause_reason == "handoff":
            lineas.append("The team was already notified about this chat; no need to notify again unless something new comes up.")
        return "\n".join(lineas)

    def _xb_ba_history(self):
        self.ensure_one()
        desde = fields.Datetime.now() - timedelta(hours=XB_HISTORY_HOURS)
        mensajes = self.env["mail.message"].sudo().search([
            ("model", "=", "discuss.channel"), ("res_id", "=", self.id), ("date", ">=", desde),
            "|", ("message_type", "=", "whatsapp_message"),
            "&", ("message_type", "=", "comment"), ("body", "ilike", XB_DRAFT_MARK),
        ], order="id desc", limit=XB_HISTORY_LIMIT).sorted("id")
        bot = self.env.ref("base.partner_root")
        entrantes = mensajes.filtered(lambda m: m.wa_message_ids.filtered(lambda w: w.message_type == "inbound"))
        # Only the customer's most recent images and PDFs go in full (they cost
        # tokens); older ones show as «[Attached: …]».
        imagenes = entrantes.attachment_ids.filtered(lambda a: (a.mimetype or "") in XB_VISION_TYPES)
        vistas = set(imagenes.sorted("id", reverse=True)[:XB_VISION_MAX].ids)
        pdfs = entrantes.attachment_ids.filtered(
            lambda a: a.mimetype == "application/pdf" and a.file_size <= XB_PDF_MAX_BYTES)
        pdf_vistos = set(pdfs.sorted("id", reverse=True)[:XB_PDF_MAX].ids)
        turnos = []
        for msg in mensajes:
            ensayo = msg.message_type == "comment"
            if ensayo and msg.author_id != bot:
                continue
            entrante = msg in entrantes
            # In rehearsal mode the replies are notes: without them the agent
            # would not remember what it said and would greet every time.
            texto = html2plaintext(self._xb_ba_strip_draft(msg.body)).strip()
            bloques = []
            otros = msg.attachment_ids.filtered(lambda a: a.id not in vistas)
            for adjunto in msg.attachment_ids.filtered(lambda a: a.id in vistas):
                bloque = self._xb_ba_image_block(adjunto)
                if bloque:
                    bloques.append(bloque)
                else:
                    otros |= adjunto
            for adjunto in otros.filtered(lambda a: a.id in pdf_vistos):
                bloques.append({"type": "document", "title": adjunto.name or "document.pdf", "source": {
                    "type": "base64", "media_type": "application/pdf",
                    "data": base64.b64encode(adjunto.sudo().raw).decode()}})
                otros -= adjunto
            if entrante:
                for adjunto in otros.filtered(lambda a: (a.mimetype or "").startswith("audio/")):
                    voz = self._xb_ba_transcribe(adjunto)
                    if voz:
                        texto = f"{texto}\n[Voice note transcript]: {voz}".strip()
                        otros -= adjunto
            if otros:
                tipos = ", ".join(sorted({self._xb_ba_attach_label(a) for a in otros}))
                texto = f"{texto}\n[Attached: {tipos}]".strip()
            if not texto and not bloques:
                continue
            if entrante:
                rol = "user"
            else:
                rol = "assistant"
                if msg.author_id != bot:
                    texto = f"[A person from the team replied ({msg.author_id.name})]: {texto}"
            if texto:
                bloques.append({"type": "text", "text": texto})
            if turnos and turnos[-1]["role"] == rol:
                turnos[-1]["content"] += bloques
            else:
                turnos.append({"role": rol, "content": bloques})
        while turnos and turnos[0]["role"] != "user":
            turnos.pop(0)
        return turnos

    @api.model
    def _xb_ba_strip_draft(self, body):
        """Body of a rehearsal note without its heading."""
        texto = str(body or "")
        if XB_DRAFT_MARK in texto:
            texto = texto.split("</p>", 1)[1] if "</p>" in texto else ""
        return texto

    @api.model
    def _xb_ba_attach_label(self, adjunto):
        tipo = adjunto.mimetype or ""
        if tipo.startswith("image/"):
            return "image"
        if tipo.startswith("audio/"):
            return "voice note"
        if tipo.startswith("video/"):
            return "video"
        if tipo == "application/pdf":
            return "PDF"
        return "file"

    def _xb_ba_transcribe(self, adjunto):
        """Text of a voice note (OpenAI). Saved on the attachment so it is paid once."""
        adjunto = adjunto.sudo()
        if (adjunto.description or "").startswith(XB_VOICE_MARK):
            return adjunto.description[len(XB_VOICE_MARK):]
        llave = self.wa_account_id.sudo().xb_ba_openai_key
        if not llave or not adjunto.raw or adjunto.file_size > XB_VOICE_MAX_BYTES:
            return ""
        try:
            resp = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {llave}"},
                data={"model": XB_VOICE_MODEL, "response_format": "text"},
                files={"file": (adjunto.name or "voice.ogg", adjunto.raw, adjunto.mimetype or "audio/ogg")},
                timeout=60)
            resp.raise_for_status()
        except Exception as e:  # noqa: BLE001 - without a transcript the customer is asked to type
            _logger.warning("xb_business_agent: transcription of attachment %s failed: %s", adjunto.id, e)
            return ""
        texto = (resp.text or "").strip()
        if texto:
            adjunto.description = XB_VOICE_MARK + texto
        return texto

    @api.model
    def _xb_ba_image_block(self, adjunto):
        """Image for Claude: longest side ≤ 1568 px and JPEG, to avoid overpaying."""
        try:
            img = Image.open(io.BytesIO(adjunto.sudo().raw))
            img = ImageOps.exif_transpose(img).convert("RGB")
            img.thumbnail((XB_VISION_SIDE, XB_VISION_SIDE))
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=85)
        except Exception:  # noqa: BLE001 - damaged image or odd format: described as an attachment
            _logger.warning("xb_business_agent: could not read image %s", adjunto.id)
            return None
        return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                             "data": base64.b64encode(buf.getvalue()).decode()}}

    # ------------------------------------------------------------------
    # The loop with Claude
    # ------------------------------------------------------------------
    def _xb_ba_client(self, acc):
        import anthropic  # lazy: the module loads even without the library
        return anthropic.Anthropic(api_key=acc.xb_ba_api_key, timeout=120, max_retries=2)

    def _xb_ba_answer(self, job):
        self.ensure_one()
        acc = self.wa_account_id.sudo()
        if not acc.xb_ba_enabled:
            job.write({"state": "skipped", "reason": "The agent is off on this number"})
            return
        if self.xb_ba_paused_until and self.xb_ba_paused_until > fields.Datetime.now():
            self._xb_ba_on_hold(job)
            return
        historial = self._xb_ba_history()
        if not historial or historial[-1]["role"] != "user":
            job.write({"state": "skipped", "reason": "Nothing new to answer"})
            return
        if not acc.xb_ba_api_key:
            raise ValueError(self.env._("The Anthropic API key is missing on the WhatsApp account"))

        job.model_name = acc.xb_ba_model
        client = self._xb_ba_client(acc)
        system = [{"type": "text", "text": acc._xb_ba_system_prompt(), "cache_control": {"type": "ephemeral"}}]
        mensajes = historial + [{"role": "system", "content": self._xb_ba_context_text()}]
        texto = ""
        for _ronda in range(XB_MAX_TOOL_ROUNDS):
            kwargs = dict(model=acc.xb_ba_model, max_tokens=8000, system=system, messages=mensajes,
                          tools=XB_TOOLS, output_config={"effort": acc.xb_ba_effort})
            if acc.xb_ba_model == "claude-haiku-5-5":
                resp = client.messages.create(**kwargs)
            else:
                # If a safety filter refuses the request, Anthropic retries it
                # on the fallback model it recommends.
                resp = client.beta.messages.create(betas=[XB_FALLBACK_BETA], fallbacks="default", **kwargs)
            job._xb_add_usage(acc.xb_ba_model, resp.usage)

            if resp.stop_reason == "refusal":
                job._xb_log("The model refused to answer.")
                self._xb_ba_tool_hand_over(job, {
                    "reason": "other", "urgent": False,
                    "summary": self.env._("The AI model refused to answer this message; please review it.")})
                texto = acc.xb_ba_hold_message or ""
                break
            usos = [b for b in resp.content if b.type == "tool_use"]
            if resp.stop_reason == "tool_use" and usos:
                mensajes.append({"role": "assistant", "content": resp.content})
                resultados = []
                for uso in usos:
                    resultado, es_error = self._xb_ba_run_tool(job, uso.name, uso.input)
                    resultados.append({"type": "tool_result", "tool_use_id": uso.id,
                                       "content": resultado, "is_error": es_error})
                mensajes.append({"role": "user", "content": resultados})
                continue
            texto = "\n\n".join(b.text for b in resp.content if b.type == "text").strip()
            break
        else:
            job._xb_log("Reached the maximum number of tool rounds.")

        if not texto:
            job.write({"state": "skipped", "reason": "The agent produced no reply"})
            return
        job.reply = texto
        self._xb_ba_deliver(job, texto)

    def _xb_ba_deliver(self, job, texto, reason=False):
        """Sends the reply, or in rehearsal mode leaves it as an internal note."""
        vals = {"reply": texto}
        if reason:
            vals["reason"] = reason
        if self.wa_account_id.sudo().xb_ba_shadow:
            self._xb_ba_post_draft(texto)
            vals["state"] = "draft"
        else:
            self._xb_ba_send(texto)
            vals["state"] = "done"
        job.write(vals)

    def _xb_ba_on_hold(self, job):
        """The customer writes again while waiting for a person.

        Every XB_HOLD_HOURS the team is reminded and, if the agent handed the chat
        over (rather than a person who is already replying), the customer is told
        the team was notified. That way nobody is left without an answer.
        """
        acc = self.wa_account_id.sudo()
        ahora = fields.Datetime.now()
        if self.xb_ba_hold_dt and self.xb_ba_hold_dt > ahora - timedelta(hours=XB_HOLD_HOURS):
            job.write({"state": "skipped", "reason": "Paused; the team was notified recently"})
            return
        texto = html2plaintext(job.message_id.body or "").strip() or "…"
        lead = self.xb_ba_lead_id.sudo()
        self._xb_ba_notify(lead or job, acc.xb_ba_user_ids | lead.user_id,
                           self.env._("%(who)s wrote again and is waiting for a person: «%(text)s»",
                                      who=self._xb_ba_who(), text=texto[:300]),
                           urgent=True)
        self.sudo().xb_ba_hold_dt = ahora
        if self.xb_ba_pause_reason == "human" or not acc.xb_ba_hold_message:
            job.write({"state": "skipped", "reason": "Paused; the team was notified"})
            return
        self._xb_ba_deliver(job, acc.xb_ba_hold_message, "Paused; the team and the customer were notified")

    def _xb_ba_run_tool(self, job, nombre, entrada):
        metodo = getattr(self, f"_xb_ba_tool_{nombre}", None)
        if not metodo:
            return f"Unknown tool: {nombre}", True
        try:
            with self.env.cr.savepoint():
                resultado = metodo(job, entrada or {})
            es_error = False
        except Exception as e:  # noqa: BLE001 - the error is explained to the model
            _logger.exception("xb_business_agent: tool %s failed", nombre)
            resultado, es_error = f"Error: {e}", True
        if not isinstance(resultado, str):
            resultado = json.dumps(resultado, ensure_ascii=False, default=str)
        job._xb_log(f"▸ {nombre}({json.dumps(entrada, ensure_ascii=False)})\n  → {resultado[:1500]}")
        return resultado, es_error

    # ------------------------------------------------------------------
    # Outgoing
    # ------------------------------------------------------------------
    def _xb_ba_send(self, texto):
        """Free-form message inside the 24 h window (no template, no cost)."""
        self.ensure_one()
        self.sudo().message_post(
            body=Markup(tools.plaintext2html(texto or "")),
            message_type="whatsapp_message",
            author_id=self.env.ref("base.partner_root").id,
            subtype_xmlid="mail.mt_comment",
        )

    def _xb_ba_post_draft(self, texto):
        """Rehearsal mode: internal note the customer does NOT get."""
        self.ensure_one()
        titulo = self.env._("AI agent rehearsal (not sent)")
        self.sudo().message_post(
            body=Markup('<p class="%s"><b>🤖 %s:</b></p>') % (XB_DRAFT_MARK, titulo)
            + Markup(tools.plaintext2html(texto)),
            message_type="comment",
            author_id=self.env.ref("base.partner_root").id,
            subtype_xmlid="mail.mt_note",
        )

    def _xb_ba_notify(self, record, users, resumen, urgent=False):
        """An activity for each person in charge, plus a message in their inbox."""
        if not users:
            return
        for user in users:
            record.sudo().activity_schedule(
                "mail.mail_activity_data_todo",
                summary=("🚨 " if urgent else "") + resumen[:120],
                note=Markup(tools.plaintext2html(resumen)),
                user_id=user.id,
            )
        prefijo = self.env._("🚨 Urgent: ") if urgent else "🔔 "
        record.sudo().message_post(
            body=Markup(tools.plaintext2html(f"{prefijo}{resumen}")),
            partner_ids=users.partner_id.ids,
            subtype_xmlid="mail.mt_comment",
        )

    def _xb_ba_alert_failure(self, job):
        self._xb_ba_notify(job, self.wa_account_id.sudo().xb_ba_user_ids,
                           self.env._("The agent could not answer %(who)s: %(error)s",
                                      who=self._xb_ba_who(), error=job.reason),
                           urgent=True)

    def _xb_ba_who(self):
        partner = self.whatsapp_partner_id.sudo()
        if partner.name and partner.name != self.whatsapp_number:
            return f"{partner.name} ({self.whatsapp_number})"
        return self.whatsapp_number

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------
    def _xb_ba_tool_register_lead(self, job, entrada):
        acc = self.wa_account_id.sudo()
        etiquetas = {"name": self.env._("Name"), "service": self.env._("Service"), "email": self.env._("Email"),
                     "city": self.env._("City"), "notes": self.env._("Notes")}
        descripcion = "\n".join(f"{etiquetas.get(k, k)}: {v}" for k, v in entrada.items() if v)
        vals = {
            "contact_name": entrada.get("name") or False,
            "email_from": entrada.get("email") or False,
            "city": entrada.get("city") or False,
        }
        lead = self.xb_ba_lead_id.sudo()
        if lead:
            lead.write({k: v for k, v in vals.items() if v})
            if descripcion:
                lead.message_post(body=Markup(tools.plaintext2html(descripcion)), subtype_xmlid="mail.mt_note")
            return {"ok": True, "note": "Data updated."}
        user = acc._xb_ba_next_user()
        # If the CRM doesn't use Leads, a record of type lead is not visible in the pipeline.
        usa_iniciativas = self.env.ref("crm.group_use_lead").sudo().all_user_ids.filtered(lambda u: not u.share)
        quien = entrada.get("name") or self.whatsapp_partner_id.name or self.whatsapp_number
        servicio = entrada.get("service")
        vals.update({
            "name": f"WhatsApp: {quien}" + (f" — {servicio}" if servicio else ""),
            "type": "lead" if usa_iniciativas else "opportunity",
            "partner_id": self.whatsapp_partner_id.id or False,
            "phone": self.whatsapp_number,
            "user_id": user.id or False,
            "team_id": acc.xb_ba_team_id.id or False,
            "company_id": acc._xb_ba_company().id,
            "medium_id": self.env["utm.medium"].sudo().search([("name", "=", "WhatsApp")], limit=1).id or False,
            "description": Markup(tools.plaintext2html(
                descripcion + "\n\n" + self.env._("(Registered by the WhatsApp agent)"))),
        })
        lead = self.env["crm.lead"].sudo().with_company(acc._xb_ba_company()).create(vals)
        self.sudo().xb_ba_lead_id = lead
        self._xb_ba_notify(lead, lead.user_id or acc.xb_ba_user_ids,
                           self.env._("New lead from WhatsApp: %s", lead.name))
        return {"ok": True, "note": "Registered."}

    def _xb_ba_type(self, tipo_id):
        tipo = self.wa_account_id.sudo().xb_ba_appointment_type_ids.filtered(lambda t: t.id == tipo_id and t.active)
        return tipo[:1]

    def _xb_ba_fmt(self, dt_utc, tz=None):
        local = pytz.utc.localize(dt_utc).astimezone(tz or self._xb_ba_tz())
        return f"{local:%A %Y-%m-%d %H:%M}"

    @api.model
    def _xb_ba_type_tz(self, tipo):
        return pytz.timezone(tipo.appointment_tz or "UTC")

    def _xb_ba_slots(self, tipo, desde=None, todos=False):
        """Free slots of the native appointment: [(start naive UTC, user)].

        Without ``todos``: few and spread out (morning, midday and afternoon of each day; 8 in total).
        """
        tz = self._xb_ba_type_tz(tipo)
        referencia = max(desde or datetime.utcnow(), datetime.utcnow())
        por_dia = {}
        for mes in tipo.sudo()._get_appointment_slots(tz.zone, reference_date=referencia):
            for semana in mes["weeks"]:
                for dia in semana:
                    for hueco in dia.get("slots", []):
                        if not hueco.get("staff_user_id"):
                            continue
                        local = tz.localize(datetime.strptime(hueco["datetime"], "%Y-%m-%d %H:%M:%S"))
                        inicio = local.astimezone(pytz.utc).replace(tzinfo=None)
                        if inicio < referencia:
                            continue
                        usuario = self.env["res.users"].browse(hueco["staff_user_id"])
                        por_dia.setdefault(local.date(), []).append((inicio, usuario))
        if todos:
            return [x for dia in sorted(por_dia) for x in sorted(por_dia[dia], key=lambda x: x[0])]
        elegidos = []
        for dia in sorted(por_dia):
            del_dia = sorted(por_dia[dia], key=lambda x: x[0])
            elegidos += [del_dia[i] for i in sorted({0, len(del_dia) // 2, len(del_dia) - 1})]
        return elegidos[:8]

    def _xb_ba_parse_day(self, texto, tipo):
        tz = self._xb_ba_type_tz(tipo)
        return tz.localize(datetime.strptime(texto[:10], "%Y-%m-%d")).astimezone(pytz.utc).replace(tzinfo=None)

    def _xb_ba_tool_list_slots(self, job, entrada):
        tipo = self._xb_ba_type(entrada.get("appointment_type_id"))
        if not tipo:
            return {"ok": False, "reason": "That appointment type is not in the list of appointments you can book."}
        desde = None
        if entrada.get("from_date"):
            try:
                desde = self._xb_ba_parse_day(entrada["from_date"], tipo)
            except ValueError:
                return {"ok": False, "reason": "The date must be YYYY-MM-DD."}
        tz = self._xb_ba_type_tz(tipo)
        libres = self._xb_ba_slots(tipo, desde)
        salida = {"appointment": tipo.name, "slots": [self._xb_ba_fmt(t, tz) for t, _u in libres],
                  "timezone": tz.zone, "duration_minutes": round(tipo.appointment_duration * 60),
                  "bookable_up_to_days": tipo.max_schedule_days}
        if not libres:
            salida["note"] = "No free slots in that range; try another date or hand over to a person."
        if tipo.is_published:
            salida["link_to_pick_another_slot"] = f"{tipo.get_base_url().rstrip('/')}/appointment/{tipo.id}"
        return salida

    def _xb_ba_tool_book_appointment(self, job, entrada):
        tipo = self._xb_ba_type(entrada.get("appointment_type_id"))
        if not tipo:
            return {"ok": False, "reason": "That appointment type is not in the list of appointments you can book."}
        pedido = (entrada.get("start") or "")[:16]
        try:
            dia = self._xb_ba_parse_day(pedido, tipo)
        except ValueError:
            return {"ok": False, "reason": "The slot must be YYYY-MM-DD HH:MM."}
        tz = self._xb_ba_type_tz(tipo)
        elegido = [(t, u) for t, u in self._xb_ba_slots(tipo, dia, todos=True)
                   if pytz.utc.localize(t).astimezone(tz).strftime("%Y-%m-%d %H:%M") == pedido]
        if not elegido:
            return {"ok": False, "reason": "That slot is no longer free; call list_slots again."}
        inicio, usuario = elegido[0]
        fin = inicio + timedelta(hours=tipo.appointment_duration)
        cliente = self.whatsapp_partner_id.sudo()
        if not cliente:
            return {"ok": False, "reason": "The contact of this chat was not found."}
        nombre = (entrada.get("name") or "").strip() or cliente.name or self.whatsapp_number
        if nombre and cliente.name in (False, "", self.whatsapp_number):
            cliente.name = nombre
        if entrada.get("email") and not cliente.email:
            cliente.email = entrada["email"]
        # The booking carries its capacity line: without it the Appointments app
        # does not see the slot as taken and offers it again.
        vals = tipo.sudo()._prepare_calendar_event_values(
            1, [{"appointment_user_id": usuario.id, "capacity_reserved": 1, "capacity_used": 1}],
            Markup(tools.plaintext2html(self.env._("Booked by the WhatsApp agent.\nWhatsApp: %s", self.whatsapp_number))),
            tipo.appointment_duration, False, self.env["appointment.invite"], None, nombre, cliente, usuario,
            inicio, fin)
        if self.xb_ba_lead_id:
            # There is an opportunity already: link the appointment instead of creating another one.
            vals.update({"opportunity_id": self.xb_ba_lead_id.id,
                         "res_model_id": self.env["ir.model"]._get_id("crm.lead"),
                         "res_id": self.xb_ba_lead_id.id})
        evento = self.env["calendar.event"].with_context(
            mail_notify_author=True, mail_create_nolog=True, mail_create_nosubscribe=True,
            allowed_company_ids=usuario.company_ids.ids,
        ).sudo().create(vals)
        if not self.xb_ba_lead_id and evento.opportunity_id:
            self.sudo().xb_ba_lead_id = evento.opportunity_id
        if not evento.opportunity_id:  # with an opportunity, Appointments already leaves the staff an activity
            self._xb_ba_notify(job, usuario, self.env._(
                "Appointment booked on WhatsApp: %(type)s, %(when)s with %(name)s",
                type=tipo.name, when=self._xb_ba_fmt(inicio, tz), name=nombre))
        salida = {"ok": True, "appointment_id": evento.id, "appointment": tipo.name,
                  "when": self._xb_ba_fmt(inicio, tz), "timezone": tz.zone, "with": usuario.name,
                  "duration_minutes": round(tipo.appointment_duration * 60)}
        if evento.videocall_location:
            salida["videocall_link"] = evento.videocall_location
        if tipo.location_id:
            salida["place"] = tipo.location_id.contact_address or tipo.location_id.name
        return salida

    def _xb_ba_my_events(self):
        partner = self.whatsapp_partner_id
        tipos = self.wa_account_id.sudo().xb_ba_appointment_type_ids
        if not partner or not tipos:
            return self.env["calendar.event"]
        return self.env["calendar.event"].sudo().search([
            ("partner_ids", "in", partner.ids), ("appointment_type_id", "in", tipos.ids),
            ("start", ">=", fields.Datetime.now())], order="start", limit=5)

    def _xb_ba_tool_my_appointments(self, job, entrada):
        citas = self._xb_ba_my_events()
        if not citas:
            return {"appointments": [], "note": "No upcoming appointments."}
        return {"appointments": [{"appointment_id": e.id, "appointment": e.appointment_type_id.name,
                                  "when": self._xb_ba_fmt(e.start, self._xb_ba_type_tz(e.appointment_type_id)),
                                  "with": e.user_id.name} for e in citas]}

    def _xb_ba_tool_cancel_appointment(self, job, entrada):
        evento = self._xb_ba_my_events().filtered(lambda e: e.id == entrada.get("appointment_id"))
        if not evento:
            return {"ok": False, "reason": "That appointment is not this person's or is already past; call my_appointments."}
        cuando = self._xb_ba_fmt(evento.start, self._xb_ba_type_tz(evento.appointment_type_id))
        evento.action_cancel_meeting(self.whatsapp_partner_id.ids)
        self._xb_ba_notify(job, evento.user_id, self.env._(
            "Appointment cancelled on WhatsApp: %(type)s, %(when)s (%(who)s)",
            type=evento.appointment_type_id.name, when=cuando, who=self._xb_ba_who()))
        return {"ok": True, "note": f"Appointment on {cuando} cancelled."}

    def _xb_ba_tool_hand_over(self, job, entrada):
        acc = self.wa_account_id.sudo()
        motivos = {
            "unknown": self.env._("The agent didn't know the answer"),
            "asks_for_person": self.env._("Asked to talk to a person"),
            "payments_or_complaints": self.env._("Payments or complaints"),
            "sensitive": self.env._("Sensitive matter"),
            "other": self.env._("Review"),
        }
        titulo = f"{motivos.get(entrada.get('reason'), motivos['other'])} · {self._xb_ba_who()}"
        lead = self.xb_ba_lead_id.sudo()
        users = acc.xb_ba_user_ids | lead.user_id
        self._xb_ba_notify(lead or job, users, f"{titulo}\n{entrada.get('summary') or ''}", bool(entrada.get("urgent")))
        # The agent does NOT go quiet: it keeps answering the rest. It only remembers the team was notified.
        self.sudo().write({"xb_ba_pause_reason": "handoff", "xb_ba_hold_dt": fields.Datetime.now()})
        if not users:
            return {"ok": False, "note": "Nobody is set up to answer; tell the person the business will reply soon."}
        return {"ok": True, "note": "The team was notified. Tell the person kindly."}
