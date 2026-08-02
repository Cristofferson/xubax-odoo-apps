# -*- coding: utf-8 -*-
from odoo import models


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _xb_calendar_company(self):
        """Company of the meeting this channel is the videocall of.

        Empty when the channel is not a meeting: a plain Discuss public channel
        is none of this module's business and is left as Odoo renders it. The
        lookup is done with ``sudo`` because the page is served to a guest, who
        cannot read ``calendar.event`` at all.
        """
        self.ensure_one()
        event = self.env["calendar.event"].sudo().search(
            [("videocall_channel_id", "=", self.id)], limit=1)
        return event._xb_calendar_company() if event else self.env["res.company"]
