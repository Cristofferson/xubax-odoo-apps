# -*- coding: utf-8 -*-
from odoo import models


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    def get_base_url(self):
        """Domain of every link that points back at this meeting.

        ``calendar`` funnels all of them through this method: the Discuss
        videocall URL (``_set_discuss_videocall_location``) and, through
        ``mail.render.mixin._render_template_postprocess``, the relative links
        of the update and cancellation emails.
        """
        if self._xb_calendar_keep_native_url():
            return super().get_base_url()
        return self._xb_calendar_company()._xb_calendar_base_url() or super().get_base_url()

    def _xb_calendar_company(self):
        """Company whose domain the links follow: the organiser's.

        ``get_base_url`` is also reached with an **empty** recordset — the link
        of a brand new meeting is built before the record exists, in
        ``get_discuss_videocall_location`` — so fall back to the active company.
        """
        event = self[:1].sudo()
        return event.user_id.company_id or self.env.company

    def _xb_calendar_keep_native_url(self):
        """An online booking keeps the domain of the website it was booked on.

        ``appointment`` (Odoo Enterprise) resolves the URL from
        ``appointment_type_id.website_id``, which is what the attendee expects:
        they booked on that website and the confirmation should point there.

        Stepping aside is also the only behaviour we can *guarantee*: whether
        this override or ``appointment``'s runs first depends on the order the
        modules happen to load in, and ``appointment`` returns its own URL
        without calling ``super()``. Deferring here gives the same result under
        either order. The field is looked up softly so the module keeps working
        without ``appointment`` installed.
        """
        return "appointment_type_id" in self._fields and bool(self[:1].sudo().appointment_type_id)
