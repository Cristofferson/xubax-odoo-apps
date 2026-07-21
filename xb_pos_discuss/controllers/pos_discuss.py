# -*- coding: utf-8 -*-
from odoo import fields, http
from odoo.http import request

from odoo.addons.web.controllers.home import Home


class XbPosDiscussHome(Home):
    """Lets the POS panel embed Discuss, and nothing else embed anything."""

    @http.route()
    def web_client(self, s_action=None, **kw):
        # Odoo answers the back office with ``X-Frame-Options: DENY`` so no page
        # can ever frame it. The POS panel is a page of the *same origin*, so on
        # its explicit request that blanket ban is swapped for the narrowest
        # permission covering that case: ``frame-ancestors 'self'``, which still
        # blocks every other domain (the same guard Odoo itself uses on the
        # login page). Nothing changes for any other request.
        response = super().web_client(s_action=s_action, **kw)
        if kw.get("xb_pos_frame") and hasattr(response, "headers"):
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
        return response


class XbPosDiscussController(http.Controller):
    """Feeds the unread badge of the POS Discuss button."""

    @http.route("/xb_pos_discuss/unread", type="jsonrpc", auth="user")
    def unread(self):
        """Return the very number the Discuss systray shows in the back office.

        Odoo does not count unread *messages*: a conversation with forty
        pending messages adds **one**, the same as a conversation with one, and
        muted or closed conversations add nothing. The formula mirrors
        ``computeGlobalCounter`` of ``mail``: the Inbox, plus one per channel
        with something pending, minus the channel mentions already counted in
        the Inbox (so a mention adds one, not two).

        Everything rests on Odoo's own read state, so what the user reads
        anywhere — Discuss on the web, on the phone, in this panel — stops
        counting everywhere.
        """
        Message = request.env["mail.message"]
        inbox = Message.search_count([("needaction", "=", True)])
        channel_mentions = Message.search_count([
            ("needaction", "=", True),
            ("model", "=", "discuss.channel"),
        ])

        now = fields.Datetime.now()
        members = request.env["discuss.channel.member"].search([
            ("is_self", "=", True),
            ("is_pinned", "=", True),
        ])
        pending_channels = sum(
            1
            for member in members
            if (not member.mute_until_dt or member.mute_until_dt <= now)
            and (member.message_unread_counter or member.channel_id.message_needaction_counter)
        )
        return {"count": max(inbox + pending_channels - channel_mentions, 0)}
