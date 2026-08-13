# -*- coding: utf-8 -*-
"""Give the agent the context of the message the customer is replying to.

A WhatsApp template sent from a business record — here a reminder — is logged
on THAT record, not on the customer's ``discuss.channel``. When the customer
answers within the 24h window, Odoo creates the channel from scratch and drops
only a "Related <document>:" link into it, never the text that was sent. The
agent is left reading a bare reply ("who chose my ring?") with no idea what it
answers.

So we mirror the outgoing greeting into the channel, as an internal note, at
the moment the channel is born.

Two design decisions worth keeping:

* **Central, not per-send.** The hook is ``_get_whatsapp_channel``, the single
  place every WhatsApp channel is born through. Mirroring at send time instead
  would only ever cover this module's reminders; here it covers every campaign
  that goes out as a template on a business record.

* **Lazy.** The channel is only seeded when it is actually created, which for
  an inbound is when the customer replies. Nobody who stays silent gets a
  channel, so a blast of a few thousand templates does not create a few
  thousand empty conversations.
"""
import logging

from markupsafe import Markup

from odoo import models, _

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _get_whatsapp_channel(self, whatsapp_number, wa_account_id, sender_name=False,
                              create_if_not_found=False, related_message=False):
        # Native routes here from BOTH the inbound webhook (create_if_not_found
        # =True, related_message = the last template sent to this number, see
        # whatsapp.account._find_active_channel) and outbound sends
        # (create_if_not_found=False, so no channel is born). We only seed a
        # channel that is genuinely NEW and was started by a template sent on a
        # business record.
        want_mirror = bool(
            create_if_not_found and related_message
            and getattr(related_message, "model", False)
            and related_message.model not in ("discuss.channel", "mailing.mailing")
            and related_message.body
        )
        pre_ids = set()
        if want_mirror:
            pre_ids = set(self.sudo().search(
                [("wa_account_id", "=", wa_account_id.id)]).ids)
        channel = super()._get_whatsapp_channel(
            whatsapp_number, wa_account_id, sender_name=sender_name,
            create_if_not_found=create_if_not_found, related_message=related_message,
        )
        if want_mirror and channel and channel.id not in pre_ids:
            try:
                channel._xb_mirror_greeting(related_message.body)
            except Exception:  # noqa: BLE001 - never break channel creation
                _logger.exception(
                    "xb_special_dates_whatsapp: could not mirror greeting into "
                    "channel %s", channel.id)
        return channel

    def _xb_mirror_greeting(self, greeting_body):
        """Post the outgoing template as an internal note, so the agent reading
        the customer's reply sees what it answers.

        ``message_type='comment'`` with the ``mail.mt_note`` subtype: it is a
        log note, so it is NOT sent back to the customer."""
        self.ensure_one()
        self.message_post(
            body=Markup("<p><b>%s</b></p>") % _("Message sent to the customer:")
            + Markup(greeting_body or ""),
            author_id=self.env.ref("base.partner_root").id,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
