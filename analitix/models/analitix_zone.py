# -*- coding: utf-8 -*-
"""Zones: the shop floor divided into places worth measuring separately.

A store is not one space. "Twelve minutes inside" tells an owner nothing;
"eleven of those twelve in front of the engagement rings, and nobody spoke to
them" tells them exactly where the money went.

As everywhere else in this addon, the number of zones is a property of the
customer's shop, not of the code. A corner shop may have two; a department
floor may have fifteen.

The shift map
-------------
An alert has to reach *a person*, and who covers the ring counter at 11:00 is
not who covers it at 19:00. ``analitix.zone.vendor`` is that map, and it is
per-zone, per-weekday and per-hour because that is how a real rota works.
"""
from datetime import timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

WEEKDAYS = [
    ("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"), ("3", "Thursday"),
    ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday"),
]


class AnalitixZone(models.Model):
    _name = "analitix.zone"
    _description = "Analitix Store Zone"
    _order = "store_id, sequence, id"

    name = fields.Char(
        required=True,
        help="What the staff of this store call it: 'Engagement Rings', "
             "'Fitting Rooms', 'Checkout'.")
    code = fields.Char(string="Reference", copy=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)

    kind = fields.Selection(
        selection=[
            ("entrance", "Entrance area"),
            ("display", "Display / counter"),
            ("fitting", "Fitting rooms"),
            ("checkout", "Checkout"),
            ("general", "General floor"),
            ("exit", "Exit area"),
        ],
        string="Zone Type", default="display", required=True,
        help="Drives sensible defaults and, from phase 4, which screen a "
             "trigger is routed to.")

    device_ids = fields.One2many(
        "analitix.device", "zone_id", string="Cameras")
    poi_ids = fields.One2many("analitix.poi", "zone_id", string="Displays")
    vendor_ids = fields.One2many(
        "analitix.zone.vendor", "zone_id", string="Shift Coverage")

    area_sqm = fields.Float(string="m²")
    engaged_seconds = fields.Integer(
        string="Engaged After (s)", default=20, required=True,
        help="Someone lingering this long is looking, not walking past. Below "
             "it the dwell is recorded but not treated as interest — a corridor "
             "zone would otherwise report everyone who crosses it as engaged.")
    lost_sale_seconds = fields.Integer(
        string="Possible Lost Sale After (s)", default=180, required=True,
        help="Dwell beyond this with nobody serving them is worth a nudge. Set "
             "it long in a browse-heavy shop and short at a counter where "
             "waiting means being ignored.")
    alert_on_dwell = fields.Boolean(
        string="Nudge On Long Dwell", default=True,
        help="Send the discreet alert when the threshold above is passed. Turn "
             "it off in a fitting room or a waiting area, where lingering is "
             "the point rather than a problem.")

    dwell_ids = fields.One2many(
        "analitix.zone.dwell", "zone_id", string="Dwell Records")
    visitors_today = fields.Integer(
        compute="_compute_stats", compute_sudo=True, string="Visits Today")
    avg_dwell_today = fields.Float(
        compute="_compute_stats", compute_sudo=True, string="Avg Dwell (s)")

    note = fields.Text(string="Notes")

    _code_store_uniq = models.Constraint(
        "unique(code, store_id)",
        "Another zone of this store already uses that reference.")
    _thresholds_ordered = models.Constraint(
        "CHECK(lost_sale_seconds >= engaged_seconds)",
        "The lost-sale threshold cannot be shorter than the engagement one.")

    @api.depends("dwell_ids")
    def _compute_stats(self):
        Dwell = self.env["analitix.zone.dwell"]
        for store in self.mapped("store_id"):
            zones = self.filtered(lambda z: z.store_id == store)
            start, end = store._period_window()
            domain = [("zone_id", "in", zones.ids), ("entered_at", ">=", start)]
            if end:
                domain.append(("entered_at", "<", end))
            grouped = Dwell._read_group(
                domain, groupby=["zone_id"],
                aggregates=["__count", "seconds:avg"])
            found = {zone.id: (count, avg or 0.0)
                     for zone, count, avg in grouped}
            for zone in zones:
                count, avg = found.get(zone.id, (0, 0.0))
                zone.visitors_today = count
                zone.avg_dwell_today = avg
        for zone in self.filtered(lambda z: not z.store_id):
            zone.visitors_today = 0
            zone.avg_dwell_today = 0.0

    @api.depends("name", "store_id.name")
    def _compute_display_name(self):
        for zone in self:
            zone.display_name = (
                "%s / %s" % (zone.store_id.name, zone.name)
                if zone.store_id else zone.name)

    @api.onchange("kind")
    def _onchange_kind(self):
        """A fitting room or a checkout queue should not nag anyone.

        Lingering there is the normal shape of the activity, not a signal that
        somebody is being ignored.
        """
        if self.kind in ("fitting", "checkout", "exit"):
            self.alert_on_dwell = False


class AnalitixZoneVendor(models.Model):
    """Who covers which zone, when.

    Kept as rows rather than a flat many2many on the zone because a rota has
    hours in it. A many2many would answer "who works this counter" but not "who
    is on it right now", and only the second question can route an alert.
    """
    _name = "analitix.zone.vendor"
    _description = "Analitix Zone Coverage"
    _order = "zone_id, weekday, hour_from"

    zone_id = fields.Many2one(
        "analitix.zone", string="Zone", required=True, index=True,
        ondelete="cascade")
    store_id = fields.Many2one(
        related="zone_id.store_id", store=True, index=True, readonly=True)
    company_id = fields.Many2one(
        related="zone_id.company_id", store=True, index=True, readonly=True)
    user_id = fields.Many2one(
        "res.users", string="Salesperson", required=True, index=True,
        ondelete="cascade")
    active = fields.Boolean(default=True)

    weekday = fields.Selection(
        selection=WEEKDAYS + [("all", "Every day")],
        string="Day", default="all", required=True)
    hour_from = fields.Float(
        string="From", default=0.0, required=True,
        help="Store local time. 0 to 24 covers the whole day.")
    hour_to = fields.Float(string="To", default=24.0, required=True)

    _hours_ordered = models.Constraint(
        "CHECK(hour_to > hour_from)",
        "The shift must end after it starts.")

    @api.constrains("hour_from", "hour_to")
    def _check_hours(self):
        for row in self:
            if not (0.0 <= row.hour_from < 24.0) or not (0.0 < row.hour_to <= 24.0):
                raise ValidationError(_(
                    "Shift hours are a 24-hour clock: 'From' between 0 and 24, "
                    "'To' above it."))

    @api.model
    def _covering(self, zone, when=None):
        """Users on duty in ``zone`` at ``when`` (default: now).

        Evaluated in the *store's* timezone. A chain's HQ reading this from
        another country must still resolve the rota the shop actually works.
        """
        store = zone.store_id
        moment = when or fields.Datetime.now()
        tz = pytz.timezone(store.tz or "UTC")
        local = pytz.utc.localize(moment).astimezone(tz)
        hour = local.hour + local.minute / 60.0
        weekday = str(local.weekday())

        rows = self.sudo().search([
            ("zone_id", "=", zone.id),
            ("active", "=", True),
            ("weekday", "in", [weekday, "all"]),
            ("hour_from", "<=", hour),
            ("hour_to", ">", hour),
        ])
        return rows.mapped("user_id")


class AnalitixZoneDwell(models.Model):
    """How long one visit spent in one zone.

    High volume — a visit touching six zones writes six rows — so it stays
    narrow and indexed, and the retention cron treats it like the crossing log.
    """
    _name = "analitix.zone.dwell"
    _description = "Analitix Zone Dwell"
    _order = "entered_at desc, id desc"
    _rec_name = "zone_id"

    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)
    zone_id = fields.Many2one(
        "analitix.zone", string="Zone", required=True, index=True,
        ondelete="cascade")
    visitor_id = fields.Many2one(
        "analitix.visitor", string="Visit", index=True, ondelete="cascade")

    entered_at = fields.Datetime(
        string="Entered", required=True, index=True,
        default=lambda self: fields.Datetime.now())
    left_at = fields.Datetime(string="Left")
    seconds = fields.Integer(
        string="Seconds", default=0, index=True,
        help="Time in the zone. Grows while the visitor is still there.")
    engaged = fields.Boolean(
        string="Engaged", index=True,
        help="Past the zone's engagement threshold: this person was looking, "
             "not walking through.")
    served = fields.Boolean(
        string="Served",
        help="A salesperson attended them, either because the edge saw a staff "
             "face beside them or because someone acknowledged the alert.")
    alert_id = fields.Many2one(
        "analitix.alert", string="Alert", ondelete="set null",
        help="The nudge this dwell produced, if it produced one.")

    _store_entered_idx = models.Index("(store_id, entered_at DESC)")
    _zone_engaged_idx = models.Index("(zone_id, engaged, entered_at)")

    @api.model
    def record(self, visitor, zone, entered_at, seconds, served=False):
        """Upsert the dwell for one visit in one zone.

        Upsert rather than append: the edge reports a running total while the
        person is still standing there, and appending would turn one browse into
        a dozen rows and a dozen alerts.
        """
        existing = self.sudo().search([
            ("visitor_id", "=", visitor.id),
            ("zone_id", "=", zone.id),
            ("entered_at", "=", entered_at),
        ], limit=1)
        vals = {
            "seconds": seconds,
            "engaged": seconds >= zone.engaged_seconds,
            "left_at": entered_at + timedelta(seconds=seconds),
        }
        if served:
            vals["served"] = True
        if existing:
            existing.write(vals)
            return existing
        vals.update({
            "store_id": zone.store_id.id,
            "zone_id": zone.id,
            "visitor_id": visitor.id,
            "entered_at": entered_at,
        })
        return self.sudo().create(vals)
