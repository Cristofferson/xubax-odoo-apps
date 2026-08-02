# -*- coding: utf-8 -*-
from odoo import models


class CalendarAttendee(models.Model):
    _inherit = "calendar.attendee"

    def get_base_url(self):
        """Domain of the links sent to this attendee.

        The invitation, reminder and date-change emails are rendered on
        ``calendar.attendee``, and their accept / decline / view links are
        written relative in the template. ``mail`` turns them into absolute
        URLs in ``_render_template_postprocess``, which asks *this* record for
        its base URL — so the attendee has to answer with the same domain as
        the meeting it belongs to, and the decision is made in a single place.
        """
        event = self[:1].sudo().event_id
        if event:
            return event.get_base_url()
        return super().get_base_url()
