# -*- coding: utf-8 -*-
from odoo import _, fields, models

from .res_company import MODE_PARAM, URL_PARAM


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    xb_calendar_link_mode = fields.Selection(
        selection=[
            ("default", "Odoo default (system base URL)"),
            ("fixed", "One domain for every meeting"),
            ("company", "One domain per company"),
        ],
        string="Meeting links domain",
        default="default",
        required=True,
        config_parameter=MODE_PARAM,
    )
    xb_calendar_link_url = fields.Char(
        string="Domain",
        config_parameter=URL_PARAM,
        help="Domain used in the meeting links. It has to be served by this "
             "same Odoo, otherwise the links will not open.",
    )
    xb_calendar_link_company_url = fields.Char(
        string="Domain of this company",
        related="company_id.xb_calendar_link_url",
        readonly=False,
    )
    xb_calendar_link_company_title = fields.Char(
        string="Videocall page title",
        related="company_id.xb_calendar_link_title",
        readonly=False,
    )

    def action_xb_calendar_update_links(self):
        """Rebuild the videocall link of the meetings that have not happened yet.

        Changing the setting only affects meetings created from then on,
        because ``videocall_location`` is stored. Writing the field by hand
        does not work either: it is computed from ``access_token``, so the ORM
        recomputes it straight back. The supported way is to ask for a
        recompute, which is what this does — and since the access token is left
        untouched, links already sent keep working, only their domain changes.
        """
        self.ensure_one()
        # The links are rebuilt from the values on screen, so persist them first.
        self.set_values()

        Event = self.env["calendar.event"].sudo()
        events = Event.search([
            ("stop", ">=", fields.Datetime.now()),
            ("videocall_location", "like", Event.DISCUSS_ROUTE),
        ])
        outdated = Event.browse()
        for event in events:
            expected = event.get_base_url()
            if expected and not event.videocall_location.startswith("%s/" % expected):
                outdated |= event

        if outdated:
            self.env.add_to_compute(outdated._fields["videocall_location"], outdated)
            outdated.mapped("videocall_location")
            outdated.flush_recordset(["videocall_location"])

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Meeting links updated"),
                "message": _(
                    "%(updated)s of the %(total)s upcoming meetings with a "
                    "videocall link were pointing somewhere else and now use "
                    "the configured domain.",
                    updated=len(outdated),
                    total=len(events),
                ),
                "sticky": False,
            },
        }
