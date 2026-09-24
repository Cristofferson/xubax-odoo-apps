# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS - WhatsApp add-on
import logging
from datetime import timedelta

from odoo import _, fields, models, tools

_logger = logging.getLogger(__name__)

# The quick-reply buttons of the follow-up template, as the customer's tap arrives
# (lower-cased). Worded unlike any other campaign's buttons so that no other module
# answers them too.
XB_FOLLOWUP_BUTTONS = {
    "me encantó": "loved",
    "quiero comentar algo": "comment",
    "algo no me gustó": "unhappy",
    "i loved it": "loved",
    "i want to comment": "comment",
    "something was not right": "unhappy",
}
# A tap counts for the follow-up sent in these last days.
XB_FOLLOWUP_REPLY_DAYS = 14


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _notify_thread(self, message, msg_vals=False, **kwargs):
        res = super()._notify_thread(message, msg_vals=msg_vals, **kwargs)
        if kwargs.get("whatsapp_inbound_msg_uid"):
            for channel in self.filtered(lambda c: c.channel_type == "whatsapp"):
                try:
                    channel._xb_followup_reply(message)
                except Exception:  # noqa: BLE001 - never break reception
                    _logger.exception("xb follow-up reply failed on channel %s", channel.id)
        return res

    def _xb_followup_reply(self, message):
        self.ensure_one()
        answer = XB_FOLLOWUP_BUTTONS.get(tools.html2plaintext(message.body or "").strip().lower())
        if not answer or not self.whatsapp_number:
            return
        # Matched by the number, not the contact: the same customer often exists twice
        # with one phone, and the conversation hangs off whichever WhatsApp found first.
        log = self.env["xb.sale.order.wa.log"].sudo().search([
            ("wa_message_id.mobile_number_formatted", "=", self.whatsapp_number),
            ("kind", "=", "followup"),
            ("failed", "=", False),
            ("reply", "=", False),
            ("wa_message_id.wa_account_id", "=", self.wa_account_id.id),
            ("date", ">=", fields.Datetime.now() - timedelta(days=XB_FOLLOWUP_REPLY_DAYS)),
        ], limit=1)
        if not log:
            return
        log.reply = answer
        order = log.order_id.sudo()
        env = self.with_context(lang=order.partner_id.lang or self.env.lang).env
        automation = self.env["xb.sale.order.wa.automation"].sudo().search([
            ("company_id", "=", order.company_id.id), ("kind", "=", "followup"),
        ], limit=1)
        seller = order.user_id
        if answer == "loved":
            text = env._("How nice to hear that! 💍 Thank you for telling us.")
        elif answer == "comment":
            text = env._("Of course! Tell us here, we are reading. 🙌")
        else:
            text = env._(
                "We are very sorry something was not as you expected. 🙏 %(seller)s will get in "
                "touch very soon to sort it out. If you prefer, tell us here what happened.",
                # First name only: "Jacqueline will get in touch", not her full name.
                seller=(seller.name or "").split(" ")[0] or order.company_id.name,
            )
        # An unhappy customer is not invited right away: the seller calls them first and
        # sends the link once it is sorted out (it travels in her activity below), so
        # everyone who answers is still invited, the unhappy ones just later.
        if automation.review_url and answer != "unhappy":
            text += "\n\n" + env._(
                "Would you help us with a review? Your experience helps other people a "
                "lot: %s", automation.review_url,
            )
        self.sudo().message_post(
            body=tools.plaintext2html(text),
            message_type="whatsapp_message",
            author_id=order.company_id.partner_id.id,
        )
        if answer in ("comment", "unhappy"):
            note = _("They answered the WhatsApp follow-up. Reply in the same WhatsApp "
                     "conversation (it stays open 24 hours) or call them.")
            if answer == "unhappy" and automation.review_url:
                note += "\n\n" + _(
                    "Once it is sorted out, send them the review link: %s",
                    automation.review_url,
                )
            order.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=fields.Date.context_today(order),
                summary=_("Unhappy customer: call them") if answer == "unhappy"
                else _("The customer wants to comment on their order"),
                note=tools.plaintext2html(note),
                user_id=seller.id or self.env.uid,
            )
        order.message_post(body=_(
            "WhatsApp follow-up answered: %s",
            dict(log._fields["reply"]._description_selection(env))[answer],
        ))
