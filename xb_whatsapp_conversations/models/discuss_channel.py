# -*- coding: utf-8 -*-
# XUBAX - WhatsApp Conversations
from odoo import _, fields, models
from odoo.tools import html2plaintext


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    xb_wac_last_dt = fields.Datetime(
        "Last message", readonly=True, copy=False, index="btree_not_null",
        help="Date of the last WhatsApp message of the conversation, sent or received.")
    xb_wac_waiting = fields.Boolean(
        "Awaiting reply", readonly=True, copy=False,
        help="The customer wrote the last message and nobody has answered yet.")
    xb_wac_last_text = fields.Char("Last message text", compute="_compute_xb_wac_last_text")

    def _compute_xb_wac_last_text(self):
        last = {}
        if self.ids:
            self.env.cr.execute("""
                SELECT DISTINCT ON (m.res_id) m.res_id, m.body
                  FROM mail_message m
                 WHERE m.model = 'discuss.channel' AND m.res_id IN %s
                   AND m.message_type = 'whatsapp_message'
              ORDER BY m.res_id, m.id DESC
            """, (tuple(self.ids),))
            last = dict(self.env.cr.fetchall())
        for channel in self:
            text = html2plaintext(last.get(channel.id) or "").strip().replace("\n", " ")
            if not text and channel.id in last:
                text = _("📎 File or image")
            channel.xb_wac_last_text = (text[:120] + "…") if len(text) > 120 else text

    def _xb_wac_refresh(self):
        """Recompute date and «awaiting reply» from the stored messages."""
        if not self.ids:
            return
        self.env.cr.execute("""
            SELECT DISTINCT ON (m.res_id) m.res_id, m.create_date,
                   (w.message_type = 'inbound' OR m.author_id = c.whatsapp_partner_id)
              FROM mail_message m
              JOIN discuss_channel c ON c.id = m.res_id
         LEFT JOIN whatsapp_message w ON w.mail_message_id = m.id
             WHERE m.model = 'discuss.channel' AND m.res_id IN %s
               AND m.message_type = 'whatsapp_message'
          ORDER BY m.res_id, m.id DESC
        """, (tuple(self.ids),))
        rows = {r[0]: r[1:] for r in self.env.cr.fetchall()}
        for channel in self:
            date, from_customer = rows.get(channel.id, (False, False))
            channel.sudo().write({"xb_wac_last_dt": date, "xb_wac_waiting": bool(from_customer)})

    def _notify_thread(self, message, msg_vals=False, **kwargs):
        if message.message_type == "whatsapp_message":
            # The customer wrote it when it comes in from WhatsApp, or when its author is
            # the customer's contact (older chats may have lost their WhatsApp log).
            for chat in self.filtered(lambda c: c.channel_type == "whatsapp"):
                chat.sudo().write({
                    "xb_wac_last_dt": message.create_date,
                    "xb_wac_waiting": bool(
                        kwargs.get("whatsapp_inbound_msg_uid")
                        or (message.author_id and message.author_id == chat.whatsapp_partner_id)),
                })
        return super()._notify_thread(message, msg_vals=msg_vals, **kwargs)

    def action_xb_wac_open(self):
        """Click on a row: open the whole chat in Discuss, ready to answer."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/odoo/action-mail.action_discuss?active_id={self.id}",
            "target": "self",
        }
