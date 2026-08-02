# -*- coding: utf-8 -*-
"""The action layer: turning what the store measured into something on a screen.

A store has several screens and they are **not interchangeable**. The one over
the ring counter, the one by the exit and the one facing the street do different
jobs, and a message sent to "the screen" is a message sent to the wrong one.
So every rule resolves a *destination* before it resolves content, and the
destination comes from the zone the event happened in.

Why a rule table rather than code
---------------------------------
The scenarios the brief lists — a flash offer when someone is about to leave
empty-handed, a bundle promotion when a group walks in, age-appropriate content,
a different loop at a quiet hour — are the *examples*, not the specification.
Every store will want its own, and a shop owner who has to call us to change
"show the finance offer after 3 minutes" instead of "after 5" will stop asking
and the feature dies. So the scenarios ship as configured rules on demo data,
and the engine that runs them knows nothing about jewellery.

Dispatch never blocks
---------------------
Everything here is queued. A slow or unreachable Xibo CMS must not be able to
delay a single crossing being counted — the whole architecture rests on outbound
integrations being unable to stall data capture (task 982).
"""
import logging
from datetime import timedelta

from odoo import api, fields, models, _

from .analitix_job import register_handler

_logger = logging.getLogger(__name__)

WEEKDAY_FIELDS = ["dow_mon", "dow_tue", "dow_wed", "dow_thu", "dow_fri",
                  "dow_sat", "dow_sun"]


class AnalitixSignageRule(models.Model):
    _name = "analitix.signage.rule"
    _description = "Analitix Signage Rule"
    _order = "store_id, sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)

    trigger = fields.Selection(
        selection=[
            ("lost_sale", "Someone is about to leave empty-handed"),
            ("group", "A group walked in"),
            ("demographic", "Visitor profile matches"),
            ("daypart", "Quiet hour / peak hour"),
            ("welcome", "A known customer arrived"),
        ],
        string="When", required=True, index=True,
        help="Which measured event fires this rule. These are the scenarios "
             "the product ships with; the conditions below are what make each "
             "one this store's own.")

    # ------------------------------------------------------------------
    # Conditions — all of them optional, all of them AND-ed
    # ------------------------------------------------------------------
    zone_ids = fields.Many2many(
        "analitix.zone", relation="analitix_rule_zone_rel",
        column1="rule_id", column2="zone_id", string="Only In Zones",
        help="Leave empty for the whole store.")
    age_bands = fields.Char(
        string="Age Bands",
        help="Comma-separated, e.g. '18-24,25-34'. Leave empty for any age. "
             "Only meaningful where the store captures demographics.")
    gender = fields.Selection(
        selection=[("female", "Female"), ("male", "Male")],
        string="Gender", help="Leave empty for any.")
    group_min_size = fields.Integer(
        string="Group Of At Least", default=0,
        help="0 for any. Set 2 to target couples and families.")
    hour_from = fields.Float(string="From Hour", default=0.0)
    hour_to = fields.Float(string="To Hour", default=24.0)
    dow_mon = fields.Boolean(string="Mon", default=True)
    dow_tue = fields.Boolean(string="Tue", default=True)
    dow_wed = fields.Boolean(string="Wed", default=True)
    dow_thu = fields.Boolean(string="Thu", default=True)
    dow_fri = fields.Boolean(string="Fri", default=True)
    dow_sat = fields.Boolean(string="Sat", default=True)
    dow_sun = fields.Boolean(string="Sun", default=True)
    quiet_below_visitors = fields.Integer(
        string="Quiet Below (visitors/h)", default=0,
        help="Only for the quiet-hour trigger: fire when the store's traffic "
             "this hour is under this figure. What counts as quiet is a "
             "property of the shop, not of the software.")

    # ------------------------------------------------------------------
    # Destination and content
    # ------------------------------------------------------------------
    target = fields.Selection(
        selection=[
            ("event_zone", "The screen covering where it happened"),
            ("exit", "The screen by the exit"),
            ("facade", "The screen facing the street"),
            ("fixed", "A specific screen"),
        ],
        string="Show It On", default="event_zone", required=True,
        help="Resolved at the moment the rule fires. 'Where it happened' is "
             "the usual answer — a bundle offer belongs on the screen the group "
             "is standing near, not on the one by the door.")
    target_zone_id = fields.Many2one(
        "analitix.zone", string="Specific Zone", ondelete="set null",
        help="Used when the destination is a specific screen.")
    layout_ref = fields.Char(
        string="Xibo Layout",
        help="Name of the layout to show. Leave empty to send the message "
             "below as an overlay instead.")
    message = fields.Char(
        string="Message",
        help="Shown when no layout is set. Placeholders: {customer}, {store}, "
             "{zone}. Remember the customer reads this.")
    duration_seconds = fields.Integer(string="Duration (s)", default=20)
    cooldown_minutes = fields.Integer(
        string="Cooldown (min)", default=10,
        help="Minimum gap between two firings of this rule on the same screen. "
             "Without it a busy hour turns the shop's signage into a flicker.")

    event_ids = fields.One2many(
        "analitix.signage.event", "rule_id", string="Firings")
    fire_count = fields.Integer(compute="_compute_fire_count", string="Firings")
    note = fields.Text(string="Notes")

    @api.depends("event_ids")
    def _compute_fire_count(self):
        data = self.env["analitix.signage.event"]._read_group(
            [("rule_id", "in", self.ids)],
            groupby=["rule_id"], aggregates=["__count"])
        mapped = {rule.id: count for rule, count in data}
        for rule in self:
            rule.fire_count = mapped.get(rule.id, 0)

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    def _matches(self, store, zone=None, visitor=None, group=None, when=None):
        """True when every configured condition holds. Empty means 'any'."""
        self.ensure_one()
        import pytz
        moment = when or fields.Datetime.now()
        tz = pytz.timezone(store.tz or "UTC")
        local = pytz.utc.localize(moment).astimezone(tz)

        if not self[WEEKDAY_FIELDS[local.weekday()]]:
            return False
        hour = local.hour + local.minute / 60.0
        if not (self.hour_from <= hour < self.hour_to):
            return False
        if self.zone_ids and zone and zone not in self.zone_ids:
            return False
        if self.zone_ids and not zone:
            return False
        if self.group_min_size and (not group or group.size < self.group_min_size):
            return False
        if self.age_bands:
            wanted = {b.strip() for b in self.age_bands.split(",") if b.strip()}
            band = visitor.age_band if visitor else False
            if not band or band not in wanted:
                return False
        if self.gender and (not visitor or visitor.gender != self.gender):
            return False
        if self.trigger == "daypart" and self.quiet_below_visitors:
            if store._visitors_this_hour() >= self.quiet_below_visitors:
                return False
        return True

    def _resolve_screen(self, zone=None):
        """Which screen this firing goes to. Empty means 'nowhere to send it'."""
        self.ensure_one()
        store = self.store_id
        if self.target == "fixed":
            target = self.target_zone_id
        elif self.target == "exit":
            target = store.zone_ids.filtered(lambda z: z.kind == "exit")[:1]
        elif self.target == "facade":
            target = store.zone_ids.filtered(lambda z: z.kind == "entrance")[:1]
        else:
            target = zone
        if target and target.screen_group_ref:
            return target
        # A rule pointing at a zone with no screen mapped is a configuration
        # gap, not an error: the store simply has no screen there yet.
        return self.env["analitix.zone"]

    def _recently_fired(self, screen):
        self.ensure_one()
        if self.cooldown_minutes <= 0:
            return False
        since = fields.Datetime.now() - timedelta(minutes=self.cooldown_minutes)
        return bool(self.env["analitix.signage.event"].sudo().search_count([
            ("rule_id", "=", self.id),
            ("zone_id", "=", screen.id),
            ("sent_at", ">=", since),
        ]))

    # ------------------------------------------------------------------
    # Firing
    # ------------------------------------------------------------------
    @api.model
    def fire(self, store, trigger, zone=None, visitor=None, group=None,
             partner=None, message=None):
        """Queue every matching rule. Returns the rules that will run.

        Queued rather than sent: a Xibo CMS that is slow or down must never be
        able to hold up the crossing that triggered it.
        """
        if not store.signage_enabled:
            return self.browse()
        rules = self.sudo().search([
            ("store_id", "=", store.id),
            ("trigger", "=", trigger),
            ("active", "=", True),
        ])
        queued = self.browse()
        for rule in rules:
            if not rule._matches(store, zone=zone, visitor=visitor, group=group):
                continue
            screen = rule._resolve_screen(zone)
            if not screen or rule._recently_fired(screen):
                continue
            self.env["analitix.job"].sudo().enqueue(
                "signage_dispatch", {
                    "rule_id": rule.id,
                    "zone_id": screen.id,
                    "visitor_id": visitor.id if visitor else False,
                    "partner_id": partner.id if partner else False,
                    "message": message,
                }, store=store,
                # Below the default: a welcome that arrives after the customer
                # has walked past the screen is worth nothing.
                priority=2)
            queued |= rule
        return queued

    @api.model
    def _run_dispatch(self, job):
        """Send one firing to its screen."""
        payload = job._payload()
        rule = self.sudo().browse(payload.get("rule_id") or 0).exists()
        zone = self.env["analitix.zone"].sudo().browse(
            payload.get("zone_id") or 0).exists()
        if not rule or not zone:
            return True
        visitor = self.env["analitix.visitor"].sudo().browse(
            payload.get("visitor_id") or 0).exists()
        partner = self.env["res.partner"].sudo().browse(
            payload.get("partner_id") or 0).exists()
        rule._dispatch(zone, visitor=visitor, partner=partner,
                       message=payload.get("message"))
        return True

    def _dispatch(self, zone, visitor=None, partner=None, message=None):
        """Actually put it on the screen, and record what happened."""
        self.ensure_one()
        store = self.store_id
        body = message or self._render(zone, partner)
        event = self.env["analitix.signage.event"].sudo().create({
            "rule_id": self.id,
            "store_id": store.id,
            "zone_id": zone.id,
            "screen_ref": zone.screen_group_ref,
            "visitor_id": visitor.id if visitor else False,
            "partner_id": partner.id if partner else False,
            "content": body,
        })
        ok, error = self.env["analitix.zone"]._send_to_screen(
            zone, body, layout_ref=self.layout_ref,
            seconds=self.duration_seconds or store.alert_screen_seconds)
        event.sudo().write({"delivered": ok, "error": error})
        return ok

    def _render(self, zone, partner=None):
        """Fill the placeholders. Never leaves a raw {token} on a shop screen."""
        self.ensure_one()
        text = self.message or self.name
        return text.format(
            customer=partner.name if partner else _("there"),
            store=self.store_id.name,
            zone=zone.name or self.store_id.name,
        ) if "{" in text else text


register_handler("signage_dispatch", "analitix.signage.rule", "_run_dispatch")


class AnalitixSignageEvent(models.Model):
    """Every firing, delivered or not.

    Kept even when delivery failed: "the screen never showed it" is exactly the
    thing a store needs to be able to see, and a log that only recorded
    successes would hide the CMS being down for a week.
    """
    _name = "analitix.signage.event"
    _description = "Analitix Signage Firing"
    _order = "sent_at desc, id desc"
    _rec_name = "content"

    rule_id = fields.Many2one(
        "analitix.signage.rule", string="Rule", required=True, index=True,
        ondelete="cascade")
    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, readonly=True)
    zone_id = fields.Many2one(
        "analitix.zone", string="Screen Zone", index=True, ondelete="set null")
    screen_ref = fields.Char(string="Screen")
    visitor_id = fields.Many2one(
        "analitix.visitor", string="Visit", ondelete="set null")
    partner_id = fields.Many2one(
        "res.partner", string="Customer", ondelete="set null")

    sent_at = fields.Datetime(
        string="Sent", required=True, index=True,
        default=lambda self: fields.Datetime.now())
    content = fields.Char(string="Content")
    delivered = fields.Boolean(string="Delivered", index=True)
    error = fields.Char(string="Error")

    _store_sent_idx = models.Index("(store_id, sent_at DESC)")
