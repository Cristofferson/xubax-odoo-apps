# -*- coding: utf-8 -*-
"""The store: the unit of analysis, of configuration and of tenancy.

Everything that differs from one customer to the next hangs off this record —
how many doors, how long someone must linger before it counts, how quiet a
device may go before it is called offline, who gets told when it does.  None of
it is a constant in the source.  When adding a field anywhere in this addon the
question to ask is the one from the master instruction: *is this different for
each customer store?  Then it is configuration, not code.*
"""
from datetime import timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AnalitixStore(models.Model):
    _name = "analitix.store"
    _description = "Analitix Store"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    name = fields.Char(required=True, tracking=True)
    code = fields.Char(
        string="Reference", copy=False, index=True,
        help="Short internal code for this store (e.g. 'MOR-01'). Used in "
             "device UIDs and in chain-wide reports.")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", string="Company", required=True, index=True,
        default=lambda self: self.env.company)
    tz = fields.Selection(
        selection=lambda self: [(t, t) for t in pytz.all_timezones],
        string="Timezone", default=lambda self: self.env.user.tz or "UTC",
        help="Timezone of the physical store. Opening hours, daily resets and "
             "the owner's reports follow this, not the reader's timezone — a "
             "chain's HQ in another timezone still sees each store's real day.")
    note = fields.Text(string="Notes")

    # ------------------------------------------------------------------
    # Layout: N doors, no fixed number
    # ------------------------------------------------------------------
    door_ids = fields.One2many("analitix.door", "store_id", string="Doors")
    device_ids = fields.One2many("analitix.device", "store_id", string="Devices")
    door_count = fields.Integer(compute="_compute_counts")
    device_count = fields.Integer(compute="_compute_counts")
    register_count = fields.Integer(compute="_compute_counts")

    area_sqm = fields.Float(
        string="Total m²",
        help="Total floor area in square meters. Enables the density KPIs "
             "(revenue and visitors per m²).")
    sales_area_sqm = fields.Float(
        string="Sales-floor m²",
        help="Selling area only, excluding storage and offices. Optional: use "
             "it when density should be measured over the sellable floor.")

    # ------------------------------------------------------------------
    # Sales attribution
    # ------------------------------------------------------------------
    match_mode = fields.Selection(
        selection=[
            ("registers", "Specific POS registers"),
            ("company", "Whole company"),
        ],
        string="Match sales by", required=True, default="registers", tracking=True,
        help="How POS sales are attributed to this store for conversion:\n"
             "• Specific POS registers: only orders from the registers below. "
             "Use this when several stores share one company.\n"
             "• Whole company: every POS order of the company. Use this when "
             "the company runs a single store.")
    register_ids = fields.Many2many(
        "pos.config", relation="analitix_store_register_rel",
        column1="store_id", column2="config_id", string="POS Registers",
        help="Registers whose tickets count toward this store's conversion. "
             "Only used when 'Match sales by' is 'Specific POS registers'.")

    # ------------------------------------------------------------------
    # Operational thresholds — per store, never hardcoded
    # ------------------------------------------------------------------
    heartbeat_interval_s = fields.Integer(
        string="Heartbeat Interval (s)", default=60, required=True,
        help="How often each edge agent of this store reports it is alive. "
             "The agent reads this value from the config endpoint, so changing "
             "it here re-tunes the fleet without touching any device.")
    offline_threshold_min = fields.Integer(
        string="Offline After (min)", default=5, required=True,
        help="A device that has not sent a heartbeat for this long is marked "
             "offline. Raise it on stores with a flaky connection so a 90-second "
             "outage does not page the technician every night.")
    degraded_threshold_min = fields.Integer(
        string="Degraded After (min)", default=2, required=True,
        help="Grace band before 'offline': the device is late but not yet "
             "presumed down. Shown amber on the technical dashboard.")
    alert_partner_ids = fields.Many2many(
        "res.partner", relation="analitix_store_alert_partner_rel",
        column1="store_id", column2="partner_id", string="Technical Contacts",
        help="Who is warned when a critical device of this store goes offline. "
             "While it is down the store's counting and conversion are not "
             "trustworthy and the customer is paying for data nobody captures.")
    alert_user_id = fields.Many2one(
        "res.users", string="Technical Owner",
        help="User who gets the Odoo activity for device incidents in this "
             "store. Leave empty to fall back to the store's creator.")

    # ------------------------------------------------------------------
    # Emergency kill switch (task 984, point 8)
    # ------------------------------------------------------------------
    capture_enabled = fields.Boolean(
        string="Capture Enabled", default=True, tracking=True, copy=False,
        help="Master switch for this store's data capture. Turning it off stops "
             "the ingest endpoint from accepting anything at all — no code "
             "deployment, no trip to the store. Use it for an incident, a "
             "malfunction, or when the customer asks to pause the system.")
    capture_paused_reason = fields.Char(
        string="Pause Reason", copy=False, tracking=True)
    capture_paused_by_id = fields.Many2one(
        "res.users", string="Paused By", readonly=True, copy=False)
    capture_paused_at = fields.Datetime(
        string="Paused On", readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Staff exclusion
    # ------------------------------------------------------------------
    staff_signature_ids = fields.One2many(
        "analitix.staff.signature", "store_id", string="Staff Signatures")
    staff_match_threshold = fields.Float(
        string="Staff Match Threshold", default=0.55, required=True,
        help="Cosine similarity above which a crossing is attributed to a known "
             "employee and excluded from the visitor count. Higher is stricter: "
             "fewer customers wrongly dropped, more staff wrongly counted.")
    exclude_staff = fields.Boolean(
        string="Exclude Staff From Counts", default=True,
        help="Keep employee crossings out of visitors and conversion. Turn it "
             "off only while calibrating: with it off, a store whose team walks "
             "in and out all day reads a conversion rate far below the truth.")

    # ------------------------------------------------------------------
    # Live occupancy over the selected period
    # ------------------------------------------------------------------
    visitors_in = fields.Integer(
        string="Visitors In", compute="_compute_live", compute_sudo=True,
        help="People who entered during the selected period (default: today, "
             "in the store's timezone). Staff crossings excluded.")
    visitors_out = fields.Integer(
        string="Visitors Out", compute="_compute_live", compute_sudo=True)
    live_occupancy = fields.Integer(
        string="Occupancy", compute="_compute_live", compute_sudo=True,
        help="Entrances minus exits over the period, never negative. On the "
             "default 'today' period this estimates who is inside right now.")
    last_event_time = fields.Datetime(
        string="Last Event", compute="_compute_live", compute_sudo=True)

    # --- health rollup, for the technical dashboard ---
    # Stored, unlike the live occupancy above, because these depend only on
    # stored data (a device's status and this store's own switch). Storing them
    # is what lets the technician filter, group and sort by health, which is the
    # whole point of a fleet dashboard; a non-stored compute could only be read
    # one record at a time.
    device_offline_count = fields.Integer(
        string="Devices Offline", compute="_compute_health", compute_sudo=True,
        store=True)
    health_state = fields.Selection(
        selection=[
            ("ok", "Healthy"),
            ("degraded", "Degraded"),
            ("down", "Down"),
            ("paused", "Paused"),
        ],
        string="Health", compute="_compute_health", compute_sudo=True,
        store=True, index=True)

    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "Another store of this company already uses that reference.")
    _offline_after_degraded = models.Constraint(
        "CHECK(offline_threshold_min >= degraded_threshold_min)",
        "'Offline After' must be at least as long as 'Degraded After'.")
    _positive_heartbeat = models.Constraint(
        "CHECK(heartbeat_interval_s > 0)",
        "The heartbeat interval must be a positive number of seconds.")

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("door_ids", "device_ids", "register_ids")
    def _compute_counts(self):
        for store in self:
            store.door_count = len(store.door_ids)
            store.device_count = len(store.device_ids)
            store.register_count = len(store.register_ids)

    @api.depends("device_ids.status", "device_ids.active", "device_ids.critical",
                 "capture_enabled")
    def _compute_health(self):
        for store in self:
            offline = store.device_ids.filtered(
                lambda d: d.active and d.status in ("offline", "never_seen"))
            store.device_offline_count = len(offline)
            if not store.capture_enabled:
                store.health_state = "paused"
            elif offline.filtered("critical"):
                store.health_state = "down"
            elif offline or store.device_ids.filtered(
                    lambda d: d.active and d.status == "degraded"):
                store.health_state = "degraded"
            else:
                store.health_state = "ok"

    def _period_window(self):
        """Return ``(start_utc, end_utc)`` for the period being displayed.

        The period comes from the ``analitix_period`` context key that the
        search filters set (today | yesterday | week | month), and the day
        boundary is the *store's* midnight, not the reader's — a regional
        manager in another timezone must still see each store's own day.
        """
        self.ensure_one()
        period = self.env.context.get("analitix_period", "today")
        tz = pytz.timezone(self.tz or self.env.user.tz or "UTC")
        now_local = pytz.utc.localize(fields.Datetime.now()).astimezone(tz)
        day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

        def to_utc(dt):
            return dt.astimezone(pytz.utc).replace(tzinfo=None)

        if period == "yesterday":
            return to_utc(day_start - timedelta(days=1)), to_utc(day_start)
        if period == "week":
            return to_utc(day_start - timedelta(days=day_start.weekday())), None
        if period == "month":
            return to_utc(day_start.replace(day=1)), None
        return to_utc(day_start), None

    def _compute_live(self):
        Event = self.env["analitix.event"]
        for store in self:
            start, end = store._period_window()
            domain = [
                ("store_id", "=", store.id),
                ("event_time", ">=", start),
                ("counted", "=", True),
            ]
            if end:
                domain.append(("event_time", "<", end))
            grouped = Event._read_group(
                domain, groupby=["direction"], aggregates=["count:sum"])
            totals = {direction: (total or 0) for direction, total in grouped}
            vin = totals.get("in", 0)
            vout = totals.get("out", 0)
            store.visitors_in = vin
            store.visitors_out = vout
            store.live_occupancy = max(vin - vout, 0)
            last = Event.search(
                [("store_id", "=", store.id)],
                order="event_time desc", limit=1)
            store.last_event_time = last.event_time or False

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains("register_ids")
    def _check_register_single_store(self):
        """A register may feed only one store, or its tickets double-count."""
        for store in self:
            for reg in store.register_ids:
                other = self.search([
                    ("id", "!=", store.id),
                    ("register_ids", "in", reg.id),
                ], limit=1)
                if other:
                    raise ValidationError(_(
                        "Register '%(reg)s' already belongs to store "
                        "'%(store)s'. A register can feed only one store, "
                        "otherwise its tickets would be counted twice.",
                        reg=reg.display_name, store=other.display_name))

    @api.constrains("staff_match_threshold")
    def _check_staff_threshold(self):
        for store in self:
            if not 0.0 < store.staff_match_threshold < 1.0:
                raise ValidationError(_(
                    "The staff match threshold is a cosine similarity: it must "
                    "sit strictly between 0 and 1."))

    # ------------------------------------------------------------------
    # Kill switch
    # ------------------------------------------------------------------
    def action_pause_capture(self):
        """Stop accepting data for these stores, right now."""
        for store in self:
            store.write({
                "capture_enabled": False,
                "capture_paused_by_id": self.env.user.id,
                "capture_paused_at": fields.Datetime.now(),
            })
            store.message_post(body=_(
                "Data capture PAUSED by %(user)s. The ingest endpoint will "
                "reject this store's devices until capture is resumed.",
                user=self.env.user.display_name))
            self.env["analitix.audit.log"].sudo().log(
                action="kill_switch", model="analitix.store", res_id=store.id,
                store=store, note=_("Capture paused: %s", store.capture_paused_reason or "-"))
        return True

    def action_resume_capture(self):
        for store in self:
            store.write({
                "capture_enabled": True,
                "capture_paused_reason": False,
                "capture_paused_by_id": False,
                "capture_paused_at": False,
            })
            store.message_post(body=_(
                "Data capture RESUMED by %s.", self.env.user.display_name))
            self.env["analitix.audit.log"].sudo().log(
                action="kill_switch", model="analitix.store", res_id=store.id,
                store=store, note=_("Capture resumed"))
        return True

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------
    @api.model
    def _generate_demo_traffic(self, store_ids, days=14):
        """Fabricate a fortnight of believable crossings for the demo stores.

        Written in Python rather than XML because the point of demo data here is
        a *shape*: a mid-morning rise, a lunch dip, an evening peak, weekends
        busier than Tuesdays, and a service door that only ever sees staff. A
        flat XML list of events would make every dashboard a straight line and
        show nothing about the product.

        Nothing here is random-seeded from the clock — the pattern is derived
        arithmetically from the hour and weekday, so re-running the demo gives
        the same curve and phase 6's screenshots stay reproducible.
        """
        Event = self.env["analitix.event"].sudo()
        stores = self.browse(store_ids).exists()
        if not stores or Event.search_count([("store_id", "in", stores.ids)]):
            return True  # already generated; never double up

        now = fields.Datetime.now().replace(minute=0, second=0, microsecond=0)
        vals_list = []
        for store in stores:
            doors = store.door_ids
            if not doors:
                continue
            counting = doors.filtered("counts_visitors") or doors
            for day_offset in range(days, 0, -1):
                day = now - timedelta(days=day_offset)
                weekday = day.weekday()
                # Sat/Sun carry roughly half again the weekday traffic.
                day_weight = 1.5 if weekday >= 5 else 1.0
                for hour in range(10, 21):  # a 10:00–20:00 trading day
                    # Two humps: late morning and early evening.
                    shape = 1.0 + 0.6 * (1 - abs(hour - 13) / 4.0) \
                            + 0.9 * (1 - abs(hour - 19) / 4.0)
                    shape = max(shape, 0.3)
                    base = int(6 * shape * day_weight * (1 + store.area_sqm / 200.0))
                    slot = day.replace(hour=hour)
                    for index, door in enumerate(counting):
                        # Split unevenly across doors: in a real mall unit the
                        # gallery door carries most of the traffic, and a flat
                        # split would hide exactly the insight this sells.
                        share = 0.65 if index == 0 else 0.35 / max(len(counting) - 1, 1)
                        entries = max(int(base * share), 1)
                        device = door.device_ids[:1]
                        if not device:
                            continue
                        for n in range(entries):
                            stamp = slot + timedelta(minutes=(n * 53) % 60)
                            vals_list.append({
                                "uuid": "demo-%s-%s-%s-in-%s" % (
                                    store.id, door.id, slot.strftime("%Y%m%d%H"), n),
                                "device_id": device.id,
                                "door_id": door.id,
                                "store_id": store.id,
                                "direction": "in",
                                "count": 1,
                                "event_time": stamp,
                                "counted": True,
                            })
                            vals_list.append({
                                "uuid": "demo-%s-%s-%s-out-%s" % (
                                    store.id, door.id, slot.strftime("%Y%m%d%H"), n),
                                "device_id": device.id,
                                "door_id": door.id,
                                "store_id": store.id,
                                "direction": "out",
                                "count": 1,
                                "event_time": stamp + timedelta(minutes=17),
                                "counted": True,
                            })
            # Staff traffic through the service door, if there is one: excluded
            # from the count, but visible, so the exclusion can be seen working.
            service = doors.filtered(lambda d: not d.counts_visitors)
            for door in service:
                device = door.device_ids[:1]
                if not device:
                    continue
                for day_offset in range(days, 0, -1):
                    day = now - timedelta(days=day_offset)
                    for hour in (9, 14, 20):
                        vals_list.append({
                            "uuid": "demo-staff-%s-%s-%s" % (
                                door.id, day.strftime("%Y%m%d"), hour),
                            "device_id": device.id,
                            "door_id": door.id,
                            "store_id": store.id,
                            "direction": "in" if hour != 20 else "out",
                            "count": 2,
                            "event_time": day.replace(hour=hour),
                            "counted": False,
                        })
        if vals_list:
            Event.create(vals_list)
        return True

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def action_view_doors(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Doors"),
            "res_model": "analitix.door",
            "view_mode": "list,form",
            "domain": [("store_id", "=", self.id)],
            "context": {"default_store_id": self.id},
        }

    def action_view_devices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Devices"),
            "res_model": "analitix.device",
            "view_mode": "list,form",
            "domain": [("store_id", "=", self.id)],
            "context": {"default_store_id": self.id},
        }

    def action_view_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Crossing Events"),
            "res_model": "analitix.event",
            "view_mode": "list,graph,pivot,form",
            "domain": [("store_id", "=", self.id)],
            "context": {"default_store_id": self.id},
        }
