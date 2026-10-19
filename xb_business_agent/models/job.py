# -*- coding: utf-8 -*-
"""Cola y bitácora del agente.

Cada mensaje entrante crea un trabajo; se atiende fuera de la petición del
webhook. Meta espera un 200 rápido y una respuesta de la IA puede tardar
decenas de segundos: si el webhook esperara, Meta reintentaría el envío y el
cliente recibiría respuestas duplicadas.
"""
import logging
import threading
import time
from datetime import timedelta

from odoo import SUPERUSER_ID, api, fields, models
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)

# USD por millón de tokens: entrada, salida, lectura de caché, escritura de caché (5 min).
XB_PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
}
# Segundos que se espera antes de contestar: si el cliente manda tres mensajes
# seguidos, se contesta UNA vez a los tres.
XB_DEBOUNCE_SECONDS = 6
XB_MAX_ATTEMPTS = 3
# Candado de Postgres: un solo proceso atiende la cola de una base a la vez
# (el hilo que se lanza al llegar el mensaje y el cron nunca contestan doble).
XB_QUEUE_LOCK = 7_314_101


def _xb_kick(dbname):
    """Atiende la cola en un hilo apenas llega el mensaje, sin esperar al cron.
    Si el proceso muere, el cron recoge lo pendiente."""
    def correr():
        time.sleep(XB_DEBOUNCE_SECONDS)
        for _intento in range(20):
            try:
                with Registry(dbname).cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    if env["xb.business.job"]._cron_process() is not False:
                        return
            except Exception:  # noqa: BLE001
                _logger.exception("xb_business_agent: falló la atención inmediata")
                return
            time.sleep(3)
    threading.Thread(target=correr, name="xb_business_agent", daemon=True).start()


class XbBusinessJob(models.Model):
    _name = "xb.business.job"
    _description = "WhatsApp agent reply (log)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    channel_id = fields.Many2one("discuss.channel", string="Conversation",
                                 ondelete="cascade", index=True)
    message_id = fields.Many2one("mail.message", string="Customer message", ondelete="set null")
    whatsapp_number = fields.Char(related="channel_id.whatsapp_number", string="Number")
    partner_id = fields.Many2one(related="channel_id.whatsapp_partner_id", string="Contact")
    state = fields.Selection([
        ("pending", "Waiting"),
        ("done", "Answered"),
        ("draft", "Rehearsal (not sent)"),
        ("skipped", "No reply"),
        ("error", "Error"),
    ], default="pending", required=True, index=True, string="Status")
    reason = fields.Char("Detail")
    reply = fields.Text("Reply")
    log = fields.Text("What it did")
    model_name = fields.Char("AI model")
    input_tokens = fields.Integer("Input tokens")
    output_tokens = fields.Integer("Output tokens")
    cache_read_tokens = fields.Integer("Cache read tokens")
    cache_write_tokens = fields.Integer("Cache write tokens")
    cost_usd = fields.Float("Cost (USD)", digits=(10, 4))
    duration = fields.Float("Duration (s)", digits=(10, 1))
    attempts = fields.Integer("Attempts")

    def _xb_add_usage(self, model, usage):
        self.ensure_one()
        vals = {
            "input_tokens": self.input_tokens + (usage.input_tokens or 0),
            "output_tokens": self.output_tokens + (usage.output_tokens or 0),
            "cache_read_tokens": self.cache_read_tokens + (getattr(usage, "cache_read_input_tokens", 0) or 0),
            "cache_write_tokens": self.cache_write_tokens + (getattr(usage, "cache_creation_input_tokens", 0) or 0),
        }
        p_in, p_out, p_cr, p_cw = XB_PRICES.get(model, XB_PRICES["claude-opus-5-5"])
        vals["cost_usd"] = (vals["input_tokens"] * p_in + vals["output_tokens"] * p_out
                            + vals["cache_read_tokens"] * p_cr
                            + vals["cache_write_tokens"] * p_cw) / 1_000_000
        self.write(vals)

    def _xb_log(self, line):
        self.ensure_one()
        self.log = f"{self.log or ''}{line}\n"

    @api.model
    def _xb_enqueue(self, channel, message):
        job = self.sudo().create({"channel_id": channel.id, "message_id": message.id})
        self.env.ref("xb_business_agent.ir_cron_xb_business_agent")._trigger(
            at=fields.Datetime.now() + timedelta(seconds=60))
        dbname = self.env.cr.dbname
        self.env.cr.postcommit.add(lambda: _xb_kick(dbname))
        return job

    @api.model
    def _cron_process(self, limit=20):
        """Atiende la cola. Devuelve False si otro proceso ya la está atendiendo."""
        cr = self.env.cr
        cr.execute("SELECT pg_try_advisory_lock(%s)", (XB_QUEUE_LOCK,))
        if not cr.fetchone()[0]:
            return False
        try:
            # Vuelve a mirar: pudo llegar otro mensaje mientras contestaba.
            for _vuelta in range(5):
                if not self._xb_process_batch(limit):
                    break
        finally:
            cr.execute("SELECT pg_advisory_unlock(%s)", (XB_QUEUE_LOCK,))
            cr.commit()
        return True

    @api.model
    def _xb_process_batch(self, limit):
        pendientes = self.sudo().search([("state", "=", "pending"), ("attempts", "<", XB_MAX_ATTEMPTS)],
                                        order="id", limit=limit)
        if not pendientes:
            return False
        # Una sola respuesta por conversación: el trabajo más nuevo lee todo el
        # historial, los anteriores quedan unidos a él.
        ultimo = {}
        for job in pendientes:
            ultimo[job.channel_id.id] = job
        for job in pendientes:
            if ultimo.get(job.channel_id.id) != job:
                job.write({"state": "skipped", "reason": "Merged into the next message"})
        self.env.cr.commit()

        for job in ultimo.values():
            inicio = time.monotonic()
            job.attempts += 1
            self.env.cr.commit()
            try:
                job.channel_id._xb_ba_answer(job)
                job.duration = time.monotonic() - inicio
                self.env.cr.commit()
            except Exception as e:  # noqa: BLE001 - un error no debe frenar la cola
                self.env.cr.rollback()
                _logger.exception("xb_business_agent: falló el trabajo %s", job.id)
                job = job.browse(job.id)
                vals = {"reason": str(e)[:500], "duration": time.monotonic() - inicio}
                if job.attempts >= XB_MAX_ATTEMPTS:
                    vals["state"] = "error"
                    job.write(vals)
                    job.channel_id._xb_ba_alert_failure(job)
                else:
                    job.write(vals)
                self.env.cr.commit()
        if self.sudo().search_count([("state", "=", "pending"), ("attempts", "<", XB_MAX_ATTEMPTS)]):
            self.env.ref("xb_business_agent.ir_cron_xb_business_agent")._trigger(
                at=fields.Datetime.now() + timedelta(seconds=60))
        return True
