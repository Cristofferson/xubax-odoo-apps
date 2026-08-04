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

import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

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

    # Screens are per zone because a store has several and they are not
    # interchangeable: the one over the ring counter and the one facing the
    # street do different jobs. Stored as the Xibo display-group name rather
    # than a Many2one, for the same reason the WhatsApp template is an id —
    # Analitix must load on an instance that has no Xibo connector at all.
    # Phase 4 builds the full trigger engine on top of this mapping.
    screen_group_ref = fields.Char(
        string="Signage Display Group",
        help="Name of the Xibo display group covering this zone. Only used "
             "when the store has the signage channel switched on. Remember "
             "that anything sent here is visible to the customer standing in "
             "front of it.")

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

    # ------------------------------------------------------------------
    # Signage delivery — one implementation, two callers
    # ------------------------------------------------------------------
    @api.model
    def _send_to_screen(self, zone, body, layout_ref=None, seconds=20):
        """Put ``body`` (or a layout) on the screen covering ``zone``.

        Returns ``(ok, error)``. Never raises: both callers — the alert channel
        and the signage rule engine — hang off the counting pipeline, and an
        unreachable CMS must not be able to stop a store counting.

        The Xibo connector is detected at runtime rather than declared as a
        dependency: Analitix is sold to stores that have no digital signage at
        all, and it has to install for them.
        """
        if not zone or not zone.screen_group_ref:
            return False, _("No screen is mapped to this zone.")
        # Xibo no acepta texto suelto: sus modos de pantalla completa y
        # superposición exigen un DISEÑO que ya exista en el CMS, y el de cinta
        # exige un dataset. Se comprueba aquí, junto a las demás cuestiones de
        # configuración y antes de tocar nada externo, porque es un hecho local
        # y porque así el fallo no aparece a media tarde disfrazado de
        # excepción de validación del conector.
        if not layout_ref:
            return False, _(
                "No Xibo layout is set. Xibo cannot put loose text on a "
                "screen: it needs a layout that already exists in the CMS. "
                "Set it on the signage rule, or on the store for the alert "
                "screen channel.")
        installed = self.env["ir.module.module"].sudo().search_count(
            [("name", "=", "xibo_connector"), ("state", "=", "installed")])
        if not installed:
            return False, _("The Xibo connector is not installed.")
        try:
            group = self.env["xibo.display.group"].sudo().search(
                [("name", "=", zone.screen_group_ref)], limit=1)
            if not group:
                return False, _(
                    "No Xibo display group named '%s'.", zone.screen_group_ref)
            server = self.env["xibo.server"].sudo().search([], limit=1)
            if not server:
                return False, _("No Xibo server is configured.")
            layout = self.env["xibo.layout"].sudo().search(
                [("name", "=", layout_ref)], limit=1)
            if not layout:
                return False, _("No Xibo layout named '%s'.", layout_ref)
            now = fields.Datetime.now()
            vals = {
                "name": (body or zone.name)[:60],
                "server_id": server.id,
                "display_mode": "overlay",
                "display_group_ids": [(6, 0, group.ids)],
                "from_dt": now,
                "to_dt": now + timedelta(seconds=seconds),
                "duration_seconds": seconds,
            }
            vals["layout_id"] = layout.id
            broadcast = self.env["xibo.broadcast"].sudo().create(vals)
            broadcast.action_send()
            return True, False
        except Exception as error:  # noqa: BLE001
            _logger.warning(
                "Analitix: signage delivery to zone %s failed: %s",
                zone.display_name, error)
            return False, str(error)[:255]

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
    # --- the expression trend, when the edge reports one ---
    emotion = fields.Char(
        string="Last Expression", readonly=True,
        help="The most recent expression the edge reported for this person "
             "while they stood here. Kept as the latest reading only: a "
             "history of somebody's face is not something this product needs "
             "in order to say 'go over'.")
    negative_readings = fields.Integer(
        string="Negative In A Row", readonly=True,
        help="Consecutive readings above the store's confidence floor that came "
             "back sad, angry or fearful. Resets to zero the moment one does "
             "not — which is the whole point: a person who frowns once and then "
             "does not is not unhappy, they were reading a price tag.")
    emotion_alert_id = fields.Many2one(
        "analitix.alert", string="Expression Nudge", readonly=True,
        ondelete="set null",
        help="Raised at most once per visit and zone. Somebody who is having a "
             "bad afternoon should not generate a nudge every thirty seconds.")

    _zone_engaged_idx = models.Index("(zone_id, engaged, entered_at)")

    #: Expressions that count as negative. Deliberately short: 'surprised' and
    #: 'disgusted' are far too easily misread from a face at a counter, and
    #: 'neutral' is what most people look like most of the time.
    NEGATIVE = ("sad", "angry", "fearful")

    @api.model
    def record(self, visitor, zone, entered_at, seconds, served=False,
               emotion=None, emotion_confidence=0.0):
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
        store = zone.store_id
        vals = {
            "seconds": seconds,
            "engaged": seconds >= zone.engaged_seconds,
            "left_at": entered_at + timedelta(seconds=seconds),
        }
        if served:
            vals["served"] = True

        # The expression trend, only where the store asked for it and only for
        # a reading the edge was confident about.
        counts = None
        if emotion and store.emotion_alert_enabled:
            trusted = emotion_confidence >= store.emotion_min_confidence
            negative = trusted and emotion in self.NEGATIVE
            previous = existing.negative_readings if existing else 0
            counts = (previous + 1) if negative else 0
            vals.update({"emotion": emotion, "negative_readings": counts})

        if existing:
            existing.write(vals)
            if counts:
                existing._nudge_if_sustained()
            return existing
        vals.update({
            "store_id": zone.store_id.id,
            "zone_id": zone.id,
            "visitor_id": visitor.id,
            "entered_at": entered_at,
        })
        dwell = self.sudo().create(vals)
        if counts:
            dwell._nudge_if_sustained()
        return dwell

    def _nudge_if_sustained(self):
        """Tell the salesperson, once, when unhappiness has actually persisted.

        Everything about the wording here is deliberate. The salesperson is told
        that somebody *may* want attention and where they are standing — never
        that a customer is angry, and never with a confidence figure that would
        invite them to treat a model's guess as a fact. What they do with it is
        the same thing they would do for any customer who looks like they are
        waiting: go over.
        """
        self.ensure_one()
        store = self.store_id
        if (self.emotion_alert_id or not store.emotion_alert_enabled
                or self.served
                or self.negative_readings < store.emotion_sustained_readings):
            return False
        alert = self.env["analitix.alert"].raise_alert(
            store, "emotion",
            _("Someone at %s may want a hand", self.zone_id.name),
            body=_(
                "Somebody has been at %(zone)s for %(mins)s minutes and has not "
                "looked comfortable while they waited.\n\nThis is a reading of "
                "a face, not a fact — the camera is wrong about this often "
                "enough that it is worth saying so. Treat it the way you would "
                "treat any customer who looks like they are waiting: go over "
                "and ask.",
                zone=self.zone_id.name, mins=max(self.seconds // 60, 1)),
            zone=self.zone_id, visitor=self.visitor_id)
        if alert:
            self.sudo().emotion_alert_id = alert.id
        return bool(alert)
