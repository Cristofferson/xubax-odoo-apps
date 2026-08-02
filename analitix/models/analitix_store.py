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
    # Phase 2 — visits, re-identification, demographics, purchase units
    # ------------------------------------------------------------------
    reid_enabled = fields.Boolean(
        string="Recognise Repeat Faces", default=True,
        help="Turn crossings into visits by matching the same anonymous face. "
             "Without it a customer who steps out for a phone call and comes "
             "back counts as three visitors, and the conversion rate reads a "
             "third of the truth.")
    reid_threshold = fields.Float(
        string="Re-identification Threshold", default=0.62, required=True,
        help="Cosine similarity above which two sightings are the same person. "
             "Stricter than the staff threshold on purpose: a wrong staff match "
             "drops one crossing, a wrong visitor match merges two strangers "
             "into one visit and corrupts every metric downstream.")
    reid_ttl_minutes = fields.Integer(
        string="Signature Retention (min)", default=180, required=True,
        help="How long an anonymous face signature is kept before it is "
             "deleted. This is the retention promise, and it is also what keeps "
             "matching fast — a store only ever compares against the people who "
             "were there recently, never against its whole history.")
    visit_gap_minutes = fields.Integer(
        string="Same-visit Gap (min)", default=30, required=True,
        help="Leaving and returning inside this gap continues the same visit. "
             "A jewellery boutique where people browse for forty minutes and a "
             "convenience store where they are in and out in ninety seconds "
             "cannot share one number.")
    max_visit_minutes = fields.Integer(
        string="Maximum Visit (min)", default=240, required=True,
        help="A visit still open after this long is closed by the nightly "
             "cron. Exits do get missed, and a visit left open forever quietly "
             "inflates the occupancy figure until it is nonsense.")

    demographics_enabled = fields.Boolean(
        string="Capture Demographics", default=False,
        help="Estimate age band, gender and expression at the entrance. Off by "
             "default: it needs a second, front-facing camera per door, and a "
             "store that has not installed one should not see empty charts "
             "suggesting the system is broken.")
    demographic_min_confidence = fields.Float(
        string="Minimum Confidence", default=0.60, required=True,
        help="Readings below this are stored but flagged unreliable, so a "
             "dashboard can leave them out explicitly rather than quietly "
             "average a coin flip into the customer's numbers.")

    group_detection_enabled = fields.Boolean(
        string="Detect Purchase Units", default=True,
        help="Treat people who cross the same door together as one buying "
             "decision. A store that counts a family of four as four visitors "
             "and one ticket reads a 25% conversion rate when the real figure "
             "was 100%.")
    group_window_seconds = fields.Integer(
        string="Together Within (s)", default=3, required=True,
        help="How close in time counts as arriving together. A wide automatic "
             "door lets a couple through side by side in under a second; a "
             "narrow one makes them file through three seconds apart.")
    group_max_size = fields.Integer(
        string="Maximum Unit Size", default=8, required=True,
        help="Ceiling on one purchase unit. Without it, a school group filing "
             "through the door becomes a single 'customer' and distorts the "
             "day's basket statistics.")

    require_liveness = fields.Boolean(
        string="Require Liveness", default=False,
        help="Reject face readings that the edge could not confirm came from a "
             "live person rather than a photograph. Meaningful from phase 3 "
             "onward, where recognition starts driving real decisions; in "
             "phase 2 the only consequence of a match is being counted once "
             "instead of twice.")
    liveness_min_score = fields.Float(
        string="Minimum Liveness", default=0.50, required=True)

    # --- phase 2 rollups ---
    visitor_ids = fields.One2many("analitix.visitor", "store_id", string="Visits")
    signature_ids = fields.One2many(
        "analitix.face.signature", "store_id", string="Face Signatures")

    # ------------------------------------------------------------------
    # Phase 3 — zones, lost sales, displays, identification, alerts
    # ------------------------------------------------------------------
    zone_ids = fields.One2many("analitix.zone", "store_id", string="Zones")
    zone_count = fields.Integer(compute="_compute_counts")

    lost_sale_enabled = fields.Boolean(
        string="Detect Lost Sales", default=True,
        help="Nudge a salesperson when somebody lingers unserved and then "
             "leaves without buying. This is the number that sells the "
             "product: not 'you had 400 visitors' but 'eleven people waited at "
             "the counter and nine were never spoken to'.")
    lost_sale_create_lead = fields.Boolean(
        string="Create CRM Leads", default=False,
        help="Open a lead for a lost sale. Only ever fires for a customer the "
             "shop can actually contact — a lead with no name and no phone is "
             "filing clutter that buries the real ones.")

    # --- alert channels ---
    #
    # Independent switches rather than one selection: a store may well want the
    # app push *and* Discuss, or Discuss for the floor and WhatsApp for the
    # manager. Any combination is legitimate, and forcing a single choice made
    # the common ones impossible.
    #
    # The first three are discreet — only the assigned salesperson perceives
    # them. The last two are not, and are labelled as such rather than hidden:
    # the shop owner decides how their own floor works, and a checkbox that
    # tells the truth about its consequence is more useful than one that is
    # absent because a developer disapproved.
    alert_use_app = fields.Boolean(
        string="Odoo Mobile App", default=True,
        help="Push notification and activity on the salesperson's phone. "
             "Discreet: only they see it.")
    alert_use_discuss = fields.Boolean(
        string="Odoo Chat (Discuss)", default=False,
        help="Direct message in Odoo's internal chat. Discreet, and it lands "
             "in the same place the team already talks to each other — which "
             "on a floor where everyone keeps Discuss open is often read "
             "faster than a push notification. Odoo's own client chimes for a "
             "new message, so this is audible on the salesperson's device "
             "without being audible in the shop.")
    alert_use_whatsapp = fields.Boolean(
        string="WhatsApp", default=False,
        help="For staff who do not keep the Odoo app open on the floor. Needs "
             "Odoo's WhatsApp module and a template.")
    alert_use_sound = fields.Boolean(
        string="Audible Chime", default=False,
        help="Ask the receiving device to play a sound. NOT DISCREET: if the "
             "salesperson's phone is not on silent, or the alert lands on a "
             "back-office computer, the customer may hear it and understand "
             "that they are being discussed. Off by default for that reason, "
             "and worth testing on the actual devices before enabling.")
    alert_use_screen = fields.Boolean(
        string="Signage Screen", default=False,
        help="Show the alert on the Xibo screen mapped to the zone. NOT "
             "DISCREET AT ALL: whatever appears there is visible to the "
             "customer standing in front of it. Use it for a message written "
             "for the customer to read, never for one about them — 'ask about "
             "our finance options', not 'unattended for three minutes'. "
             "Requires the Xibo connector.")
    alert_fallback_user_id = fields.Many2one(
        "res.users", string="Fallback Recipient",
        help="Where an alert goes when nobody is rostered on that zone. "
             "Without one, alerts for uncovered zones are recorded but never "
             "reach a person.")
    alert_cooldown_minutes = fields.Integer(
        string="Alert Cooldown (min)", default=5, required=True,
        help="Minimum gap between alerts of the same kind to the same person. "
             "A salesperson buzzed every ninety seconds stops reading them, "
             "which is worse than not sending them at all.")
    alert_missed_after_minutes = fields.Integer(
        string="Count As Missed After (min)", default=15, required=True,
        help="An unacknowledged alert becomes 'missed' after this long. Kept "
             "honest on purpose: a report that only counted the alerts that "
             "went well would be the most flattering and least useful version "
             "of the truth.")
    # Deliberately an Integer rather than a Many2one to whatsapp.template.
    # Analitix does not depend on Odoo's WhatsApp module — this is sold to
    # stores that will not have it, and a relational field to a model that may
    # not exist makes the addon refuse to load at all. The id is resolved
    # defensively at send time. The cost is a plain number instead of a picker;
    # the alternative is an app half the market cannot install.
    alert_whatsapp_template_id = fields.Integer(
        string="WhatsApp Template ID",
        help="Numeric id of the WhatsApp template to send. Find it in "
             "WhatsApp → Templates: it is the last number in the URL when the "
             "template is open. Only used when the WhatsApp channel is "
             "selected and Odoo's WhatsApp module is installed.")
    alert_screen_seconds = fields.Integer(
        string="Screen Duration (s)", default=20, required=True,
        help="How long an alert stays on the signage screen.")
    alert_ids = fields.One2many("analitix.alert", "store_id", string="Alerts")

    # --- checkout attribution and identification ---
    checkout_match_enabled = fields.Boolean(
        string="Attribute Tickets To Visits", default=True,
        help="Tie each ticket to the visit that produced it. Anonymous: it "
             "answers 'does the profile that stops at the window actually buy' "
             "without anybody's name. Falls back to the purchase unit when "
             "there is no till camera.")
    checkout_match_threshold = fields.Float(
        string="Till Match Threshold", default=0.66, required=True,
        help="Stricter than the door threshold: attributing a ticket to the "
             "wrong visit corrupts the conversion analysis rather than merely "
             "splitting a visit in two.")
    identify_customers = fields.Boolean(
        string="Identify Returning Customers", default=False,
        help="Link a face signature to a res.partner when the customer hands "
             "over their details at the till, so the shop recognises them at "
             "the door next time. OFF by default and deliberately so: a store "
             "that only bought the analytics should never acquire a biometric "
             "customer index by accident.")
    identified_ttl_days = fields.Integer(
        string="Identified Retention (days)", default=365, required=True,
        help="How long an identified signature is kept. It outlives the "
             "anonymous window — that is what makes recognition possible — but "
             "not forever, and the same expiry job enforces it.")
    greet_known_customers = fields.Boolean(
        string="Nudge On Known Customer", default=True,
        help="Tell the salesperson when a customer they know walks in, with "
             "their name and last purchase, so they can greet them properly.")

    # ------------------------------------------------------------------
    # Phase 4 — the action layer
    # ------------------------------------------------------------------
    signage_enabled = fields.Boolean(
        string="Drive The Screens", default=False,
        help="Let measured events change what the shop's screens are showing. "
             "Off until the store has mapped a screen to at least one zone — "
             "rules that resolve to nowhere are worse than no rules.")
    signage_rule_ids = fields.One2many(
        "analitix.signage.rule", "store_id", string="Signage Rules")
    signage_rule_count = fields.Integer(compute="_compute_counts")

    welcome_alone_only = fields.Boolean(
        string="Greet By Name Only If Alone", default=True,
        help="A screen that says 'Welcome back, Gustavo' while Gustavo is "
             "standing there with somebody has just told that person something "
             "about him. When he is not alone the screen stays neutral and the "
             "personal greeting goes to the salesperson instead.")
    welcome_group_seconds = fields.Integer(
        string="Arrived-together Window (s)", default=5, required=True,
        help="How close behind a known customer another arrival counts as "
             "'with them' for the greeting rule above.")

    attendance_enabled = fields.Boolean(
        string="Log Staff Attendance", default=False,
        help="Turn employee crossings at the staff door into hr.attendance "
             "check-ins and check-outs. Off by default: a store that has not "
             "agreed this with its team should not start recording their hours "
             "because a camera was installed.")
    attendance_door_id = fields.Many2one(
        "analitix.door", string="Staff Door",
        domain="[('store_id', '=', id)]",
        help="Which entrance counts for attendance. Leave empty to accept any "
             "door — right for a small shop with one way in.")
    attendance_min_gap_minutes = fields.Integer(
        string="Ignore Repeats Within (min)", default=10, required=True,
        help="Somebody stepping out for a moment should not close and reopen "
             "their working day.")
    attendance_max_hours = fields.Integer(
        string="Maximum Shift (h)", default=12, required=True,
        help="A shift still open after this long is closed by the nightly job. "
             "Exits do get missed, and an employee who appears to have worked "
             "fifty hours makes any payroll reading it wrong.")

    value_report_enabled = fields.Boolean(
        string="Send The Monthly Report", default=True,
        help="Mail the owner a plain-language summary each month: visitors, "
             "conversion, walk-outs spotted and rescued, and roughly what that "
             "was worth. This is the report that shows the subscription paying "
             "for itself.")
    report_partner_ids = fields.Many2many(
        "res.partner", relation="analitix_store_report_partner_rel",
        column1="store_id", column2="partner_id", string="Report Recipients",
        help="Who receives the monthly value report. The owner, usually — it "
             "is written for somebody who does not open dashboards.")
    value_report_ids = fields.One2many(
        "analitix.value.report", "store_id", string="Monthly Reports")

    # --- behaviour signals ---
    anomaly_detection_enabled = fields.Boolean(
        string="Flag Unusual Behaviour", default=False,
        help="Notice patterns worth a second look: in and out repeatedly, a "
             "long stop at an expensive case with nobody nearby, a group that "
             "arrives together and scatters. Anonymous and about behaviour, "
             "never about people — the named watch list is a separate feature.")
    anomaly_window_minutes = fields.Integer(
        string="Behaviour Window (min)", default=60, required=True)
    anomaly_reentry_count = fields.Integer(
        string="Re-entries Before Flagging", default=3, required=True)
    anomaly_dwell_seconds = fields.Integer(
        string="Unattended Stop (s)", default=300, required=True)
    anomaly_dispersal_zones = fields.Integer(
        string="Zones Before Dispersal", default=3, required=True)

    # ------------------------------------------------------------------
    # Phase 5 — the watch list
    #
    # The only feature in Analitix that names a specific person, so every
    # setting here is tuned toward doing nothing rather than doing something
    # wrong. Off by default, stricter than any other threshold, liveness
    # required, and the recipients are named explicitly instead of inherited
    # from the store's ordinary alert routing.
    # ------------------------------------------------------------------
    watchlist_enabled = fields.Boolean(
        string="Use A Watch List", default=False,
        help="Recognise people a manager has deliberately added after a "
             "documented incident, and tell a named, restricted group when one "
             "of them comes in. Off by default, and it should stay off unless "
             "the store has a real reason and a person accountable for it.")
    watchlist_threshold = fields.Float(
        string="Watch-list Threshold", default=0.80, required=True,
        help="Deliberately far stricter than ordinary re-identification. A "
             "wrong re-identification merges two visits; a wrong match here "
             "puts an innocent person under suspicion, so this errs heavily "
             "towards missing a real match rather than inventing one.")
    watchlist_min_liveness = fields.Float(
        string="Watch-list Liveness", default=0.70, required=True,
        help="Readings below this are never checked against the list at all. "
             "A photograph held up to a camera must not be able to put a real "
             "person under suspicion.\n"
             "Note that cameras which do not report a liveness score at all "
             "send zero, so with any value above zero here the list matches "
             "nothing. That is the safe way round — but if your edge agents do "
             "not do liveness, lowering this is a decision to make knowingly "
             "rather than a number to nudge until matches appear.")
    watchlist_user_ids = fields.Many2many(
        "res.users", relation="analitix_store_watchlist_user_rel",
        column1="store_id", column2="user_id", string="Watch-list Recipients",
        domain="[('share', '=', False)]",
        help="The only people told about a match. Named one by one on purpose: "
             "a match is not commercial information and does not follow the "
             "ordinary zone rota to whoever happens to be on the floor.")
    watchlist_review_days = fields.Integer(
        string="Review Every (days)", default=90, required=True,
        help="How long before a new entry is put back in front of a human to "
             "confirm it still belongs on the list.")
    watchlist_expiry_days = fields.Integer(
        string="Entries Expire After (days)", default=365, required=True,
        help="An entry stops matching automatically after this. A list that "
             "only ever grows is a list nobody trusts and nobody prunes.")
    watchlist_max_days = fields.Integer(
        string="Maximum Without Review (days)", default=730, required=True,
        help="Hard ceiling: no entry can be set to run longer than this "
             "without somebody looking at it again.")
    watch_person_ids = fields.One2many(
        "analitix.watch.person", "store_id", string="Watch List")
    watch_person_count = fields.Integer(compute="_compute_counts")

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
    _positive_reid_ttl = models.Constraint(
        "CHECK(reid_ttl_minutes > 0)",
        "Face signatures must expire: the retention window has to be positive.")
    _visit_gap_under_max = models.Constraint(
        "CHECK(max_visit_minutes >= visit_gap_minutes)",
        "The maximum visit length cannot be shorter than the same-visit gap.")
    _group_size_sane = models.Constraint(
        "CHECK(group_max_size >= 1)",
        "A purchase unit holds at least one person.")

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("door_ids", "device_ids", "register_ids", "zone_ids",
                 "signage_rule_ids")
    def _compute_counts(self):
        for store in self:
            store.door_count = len(store.door_ids)
            store.device_count = len(store.device_ids)
            store.register_count = len(store.register_ids)
            store.zone_count = len(store.zone_ids)
            store.signage_rule_count = len(store.signage_rule_ids)
            store.watch_person_count = len(store.watch_person_ids)

    def _visitors_this_hour(self):
        """Counted visitors in the hour so far — the quiet/peak signal."""
        self.ensure_one()
        since = fields.Datetime.now().replace(minute=0, second=0, microsecond=0)
        return self.env["analitix.event"].sudo().search_count([
            ("store_id", "=", self.id),
            ("direction", "=", "in"),
            ("counted", "=", True),
            ("event_time", ">=", since),
        ])

    # ------------------------------------------------------------------
    # Lookups the rest of the addon needs
    # ------------------------------------------------------------------
    @api.model
    def _for_pos_config(self, config):
        """Which store a POS register's tickets belong to, if any.

        Mirrors the two attribution modes: an explicit register list, or the
        whole company. Returns an empty recordset for a register nobody has
        wired to a store, which is the normal state on an instance where only
        some shops bought Analitix.
        """
        if not config:
            return self.browse()
        store = self.sudo().search([
            ("match_mode", "=", "registers"),
            ("register_ids", "in", config.id),
        ], limit=1)
        if store:
            return store
        return self.sudo().search([
            ("match_mode", "=", "company"),
            ("company_id", "=", config.company_id.id),
        ], limit=1)

    def _average_ticket(self, days=30):
        """This store's recent average ticket.

        Used to put a number on a lost sale. It is an estimate and is labelled
        as one everywhere it surfaces: what a sale that never happened would
        have been worth cannot be known, and quoting it to the cent would be
        dishonest.
        """
        self.ensure_one()
        since = fields.Datetime.now() - timedelta(days=days)
        rows = self.env["analitix.hourly"].sudo().search([
            ("store_id", "=", self.id), ("hour", ">=", since),
            ("tickets", ">", 0),
        ])
        tickets = sum(rows.mapped("tickets"))
        if not tickets:
            return 0.0
        return sum(rows.mapped("revenue")) / tickets

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

    @api.constrains("watchlist_user_ids")
    def _check_watchlist_recipients(self):
        """Everyone told about a match must be able to open the entry.

        Alerting somebody who cannot read the record is worse than not alerting
        them: they are told a person in the shop is 'worth a look' and given no
        way to see why, which is exactly how a discreet prompt turns into a
        rumour.
        """
        group = self.env.ref("analitix.group_security", raise_if_not_found=False)
        if not group:
            return
        for store in self:
            outsiders = store.watchlist_user_ids.filtered(
                lambda user: group not in user.group_ids)
            if outsiders:
                raise ValidationError(_(
                    "%(names)s cannot open watch-list entries, so telling them "
                    "about a match would be a warning with no explanation "
                    "attached. Give them the Analitix security role first, or "
                    "leave them off this list.",
                    names=", ".join(outsiders.mapped("display_name"))))

    @api.constrains("watchlist_threshold", "watchlist_min_liveness")
    def _check_watchlist_thresholds(self):
        for store in self:
            if not 0.0 < store.watchlist_threshold < 1.0:
                raise ValidationError(_(
                    "The watch-list threshold is a cosine similarity: it must "
                    "sit strictly between 0 and 1."))
            if store.watchlist_threshold < store.reid_threshold:
                raise ValidationError(_(
                    "The watch-list threshold cannot be looser than ordinary "
                    "re-identification. Naming a person has to be harder than "
                    "counting one, not easier."))

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

        vals_list = []
        for store in stores:
            doors = store.door_ids
            if not doors:
                continue
            counting = doors.filtered("counts_visitors") or doors
            # Built in the STORE's timezone, not the server's.
            #
            # A trading day runs 10:00–20:00 local. Generating those hours as if
            # they were UTC puts a Mexican shop's evening peak at four in the
            # morning, and — worse — means that when the server clock is past
            # midnight UTC but the shop is still open, "today" comes out empty
            # and every store card reads zero visitors.
            tz = pytz.timezone(store.tz or "UTC")
            local_now = pytz.utc.localize(
                fields.Datetime.now()).astimezone(tz).replace(
                    minute=0, second=0, microsecond=0, tzinfo=None)

            def to_utc(stamp, _tz=tz):
                return _tz.localize(stamp).astimezone(pytz.utc).replace(
                    tzinfo=None)

            # Down to and including today: a demo whose newest traffic is from
            # yesterday opens on a store card reading "0 visitors today", which
            # is exactly what a broken installation looks like.
            for day_offset in range(days, -1, -1):
                day = local_now - timedelta(days=day_offset)
                weekday = day.weekday()
                # Sat/Sun carry roughly half again the weekday traffic.
                day_weight = 1.5 if weekday >= 5 else 1.0
                # Today stops at the hour the shop has actually reached.
                last_hour = local_now.hour if day_offset == 0 else 20
                for hour in range(10, min(last_hour, 20) + 1):
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
                                "event_time": to_utc(stamp),
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
                                "event_time": to_utc(
                                    stamp + timedelta(minutes=17)),
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
                    day = local_now - timedelta(days=day_offset)
                    for hour in (9, 14, 20):
                        vals_list.append({
                            "uuid": "demo-staff-%s-%s-%s" % (
                                door.id, day.strftime("%Y%m%d"), hour),
                            "device_id": device.id,
                            "door_id": door.id,
                            "store_id": store.id,
                            "direction": "in" if hour != 20 else "out",
                            "count": 2,
                            "event_time": to_utc(day.replace(hour=hour)),
                            "counted": False,
                        })
        if vals_list:
            Event.create(vals_list)
        self.browse(stores.ids)._generate_demo_visits()
        return True

    def _generate_demo_visits(self, days=3):
        """Build visits, profiles and purchase units over the recent demo days.

        Only the last few days, not the whole fortnight: the point is to show
        what phase 2 produces, and a signature per visitor for two weeks would
        be tens of thousands of rows that make the demo database slow to open
        for no extra insight.

        The one store with demographics on is the multi-door one, so a reviewer
        can see both configurations side by side — a store that has not bought
        the front-facing cameras and one that has.
        """
        Visitor = self.env["analitix.visitor"].sudo()
        Group = self.env["analitix.visit.group"].sudo()
        Demographic = self.env["analitix.demographic"].sudo()
        Signature = self.env["analitix.face.signature"].sudo()
        crypto = self.env["analitix.crypto"]

        bands = ["18-24", "25-34", "25-34", "35-44", "35-44", "45-54", "55-64"]
        genders = ["female", "male", "female", "male", "unknown"]
        moods = ["neutral", "neutral", "happy", "neutral", "sad"]

        now = fields.Datetime.now().replace(minute=0, second=0, microsecond=0)
        for store in self:
            if Visitor.search_count([("store_id", "=", store.id)]):
                continue
            doors = store.door_ids.filtered("counts_visitors")
            if not doors:
                continue
            if len(store.door_ids) > 1:
                store.demographics_enabled = True
            counter = 0
            for day_offset in range(days, 0, -1):
                for hour in range(11, 20, 2):
                    slot = now - timedelta(days=day_offset)
                    slot = slot.replace(hour=hour)
                    for index in range(6):
                        counter += 1
                        door = doors[counter % len(doors)]
                        entered = slot + timedelta(minutes=index * 7)
                        # A deterministic pseudo-vector, so the demo is
                        # reproducible for phase 6's screenshots.
                        vector = crypto.normalize([
                            ((counter * 37 + i * 13) % 100) / 100.0 - 0.5
                            for i in range(32)])
                        signature = Signature.create({
                            "reference": "DEMO-%s-%05d" % (store.code, counter),
                            "store_id": store.id,
                            "embedding": crypto.encrypt_vector(vector),
                            "embedding_dim": len(vector),
                            "first_seen": entered,
                            "last_seen": entered,
                            "expires_at": entered + timedelta(
                                minutes=store.reid_ttl_minutes),
                            "door_ids": [(6, 0, door.ids)],
                        })
                        reading = False
                        if store.demographics_enabled:
                            reading = Demographic.create({
                                "store_id": store.id,
                                "door_id": door.id,
                                "captured_at": entered,
                                "age_band": bands[counter % len(bands)],
                                "age_confidence": 0.72 + (counter % 5) / 50.0,
                                "gender": genders[counter % len(genders)],
                                "gender_confidence": 0.70 + (counter % 7) / 50.0,
                                "emotion": moods[counter % len(moods)],
                                "emotion_confidence": 0.60 + (counter % 4) / 50.0,
                                "liveness_score": 0.9,
                            })
                        visit = Visitor.create({
                            "store_id": store.id,
                            "door_id": door.id,
                            "signature_id": signature.id,
                            "entered_at": entered,
                            "exited_at": entered + timedelta(
                                minutes=6 + (counter % 23)),
                            "state": "left",
                            "demographic_id": reading.id if reading else False,
                            "is_returning": counter % 5 == 0,
                        })
                        # Every third arrival brings someone with them, which is
                        # roughly what a real store sees and enough to make the
                        # purchase-unit charts say something.
                        if counter % 3 == 0:
                            group = Group.create({
                                "store_id": store.id,
                                "door_id": door.id,
                                "entered_at": entered,
                                "visitor_ids": [(6, 0, visit.ids)],
                                "size": 1,
                            })
                            companion = Visitor.create({
                                "store_id": store.id,
                                "door_id": door.id,
                                "entered_at": entered,
                                "exited_at": visit.exited_at,
                                "state": "left",
                                "visit_group_id": group.id,
                            })
                            group.write({"size": 2})
                            companion.write({"visit_group_id": group.id})
                        else:
                            Group.create({
                                "store_id": store.id,
                                "door_id": door.id,
                                "entered_at": entered,
                                "visitor_ids": [(6, 0, visit.ids)],
                                "size": 1,
                            })
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

    def action_view_zones(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Zones"),
            "res_model": "analitix.zone",
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
