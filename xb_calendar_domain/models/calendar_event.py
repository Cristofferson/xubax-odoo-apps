# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    xb_calendar_company_id = fields.Many2one(
        "res.company",
        string="Meeting Brand",
        index="btree_not_null",
        help="Brand this meeting goes out under: its domain is the one written "
             "into the videocall link and into the invitation, reminder and "
             "update emails, and its name is the one the videocall page "
             "announces.\n"
             "A new meeting starts with the company selected in the top bar — "
             "the same one the link preview is built with. Left empty, the "
             "meeting follows the company of its Organiser, which is how "
             "meetings created before this field behave.",
    )

    xb_calendar_brand_visible = fields.Boolean(
        string="Brand Can Be Chosen",
        compute="_compute_xb_calendar_brand_visible",
        help="Technical field: a meeting only shows its brand where picking "
             "one means something, that is with one domain per company and "
             "more than one company to choose from.",
    )

    @api.model
    def default_get(self, fields_list):
        """Brand of a new meeting: the company on the top bar.

        That is the company Odoo itself builds the on-screen link with before
        the meeting is saved — ``get_discuss_videocall_location`` runs on an
        empty recordset, which falls back to ``self.env.company`` — so
        starting from it is what makes the saved link match the previewed one.

        Deliberately here and **not** in a ``default=`` on the field: adding a
        stored column makes Odoo fill it in on every row that already exists
        (``models._init_column``, which reads ``field.default`` and says in its
        own comment that it should have used ``default_get``). Every meeting in
        the database would have been stamped with whichever company happened to
        be active during the upgrade, quietly moving the links of the ones
        organised by somebody else. From here, only genuinely new meetings get
        a brand — ``create`` reaches this through
        ``_add_missing_default_values`` — and the existing ones stay empty and
        keep following their organiser.

        Left empty outside the per-company mode: there the brand decides
        nothing, and a value stored now would silently start deciding if the
        setting were switched later.
        """
        res = super().default_get(fields_list)
        if (
            "xb_calendar_company_id" in fields_list
            and not res.get("xb_calendar_company_id")
            and self.env["res.company"]._xb_calendar_mode() == "company"
        ):
            res["xb_calendar_company_id"] = self.env.company.id
        return res

    def _compute_xb_calendar_brand_visible(self):
        visible = (
            self.env["res.company"]._xb_calendar_mode() == "company"
            and self.env["res.company"].sudo().search_count([]) > 1
        )
        for event in self:
            event.xb_calendar_brand_visible = visible

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
        """Company whose domain and name the links of this meeting follow.

        The brand chosen on the meeting wins; a meeting without one — every
        meeting created before the field existed — keeps following its
        organiser, so installing this version changes nothing on its own.

        ``get_base_url`` is also reached with an **empty** recordset — the link
        of a brand new meeting is built before the record exists — so fall
        back to the active company, which is also the brand a new meeting
        starts with.
        """
        event = self[:1].sudo()
        return (
            event.xb_calendar_company_id
            or event.user_id.company_id
            or self.env.company
        )

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

    # -- Keeping the link in step with the brand ------------------------------

    def write(self, vals):
        """Rebuild the videocall link when the meeting changes hands.

        ``videocall_location`` is stored and computed from ``videocall_source``
        and ``access_token`` alone, so without this a meeting that changed
        brand — or organiser — kept the domain it was born with, and nothing
        on screen said so.
        """
        res = super().write(vals)
        if {"xb_calendar_company_id", "user_id"} & vals.keys():
            self._xb_calendar_refresh_links()
        return res

    def _xb_calendar_refresh_links(self):
        """Point the Discuss videocall links at the domain that applies now.

        Only the links Odoo itself issued are touched: a meeting held on Meet
        or Zoom keeps the address somebody typed in. The access token is left
        alone, so the invitations already sent keep working and only the
        domain in front of them changes — the same guarantee the settings
        button gives.
        """
        if self.env["res.company"]._xb_calendar_mode() == "default":
            return
        outdated = self.browse()
        for event in self:
            location = event.videocall_location or ""
            if self.DISCUSS_ROUTE not in location:
                continue
            expected = event.get_base_url()
            if expected and not location.startswith("%s/" % expected):
                outdated |= event
        if outdated:
            self.env.add_to_compute(outdated._fields["videocall_location"], outdated)
            outdated.mapped("videocall_location")
            outdated.flush_recordset(["videocall_location"])

    @api.onchange("xb_calendar_company_id")
    def _onchange_xb_calendar_company_id(self):
        """Show the new domain on the form as soon as the brand is picked.

        ``write`` is what makes it true in the database; this is so the field
        on screen stops disagreeing with it in the meantime — which is the
        very mismatch this brand field exists to end.
        """
        for event in self:
            location = event.videocall_location or ""
            if self.DISCUSS_ROUTE not in location or not event.access_token:
                continue
            base = event._xb_calendar_company()._xb_calendar_base_url()
            if base:
                event.videocall_location = "%s/%s/%s" % (
                    base, self.DISCUSS_ROUTE, event.access_token)
