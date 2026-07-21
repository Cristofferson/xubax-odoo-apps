# -*- coding: utf-8 -*-
from odoo import fields, http
from odoo.http import request


class XbPosDiscussController(http.Controller):
    """Feeds the unread badge of the POS Discuss button."""

    @http.route("/xb_pos_discuss/unread", type="jsonrpc", auth="user")
    def unread(self):
        """Return the number of unread Discuss messages of the current user.

        The count comes from ``discuss.channel.member.message_unread_counter``,
        Odoo's own read state, instead of a private flag: whatever the user
        reads in Discuss (web, mobile, systray) stops counting here, and what
        they read in the POS panel stops counting there. Muted channels are
        skipped, like the native messaging menu does.
        """
        members = request.env["discuss.channel.member"].search([("is_self", "=", True)])
        now = fields.Datetime.now()
        count = sum(
            member.message_unread_counter
            for member in members
            if not member.mute_until_dt or member.mute_until_dt <= now
        )
        return {"count": count}
