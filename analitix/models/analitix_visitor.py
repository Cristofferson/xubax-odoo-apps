# -*- coding: utf-8 -*-
"""A visit: one person, inside the store, once.

The difference between a *crossing* and a *visit* is the whole point of this
phase. Crossings are what the camera sees; visits are what the owner is asking
about when they say "how many people came in today". Somebody who steps out for
a phone call and comes back is one visit, not three, and a store that counts it
as three reports a conversion rate a third of the truth.

A visit is pseudonymous throughout this phase: it points at an anonymous,
expiring signature and carries no name. Phase 3 adds the optional bridge to a
``res.partner`` for a customer who handed over their details at the till, and
keeps that a separate, deliberate step.
"""
from datetime import timedelta

from odoo import api, fields, models, _


class AnalitixVisitor(models.Model):
    _name = "analitix.visitor"
    _description = "Analitix Visit"
    _order = "entered_at desc, id desc"
    _rec_name = "display_reference"

    display_reference = fields.Char(
        string="Visit", compute="_compute_display_reference", store=True)
    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)
    door_id = fields.Many2one(
        "analitix.door", string="Entry Door", index=True, ondelete="set null",
        help="The entrance this visit began at. Kept even after the person has "
             "moved on, because 'which door brings the customers who buy' is a "
             "question the owner will eventually ask.")
    exit_door_id = fields.Many2one(
        "analitix.door", string="Exit Door", ondelete="set null")

    signature_id = fields.Many2one(
        "analitix.face.signature", string="Signature", index=True,
        ondelete="set null",
        help="The anonymous handle this visit was matched to. It expires on the "
             "store's retention schedule; the visit itself survives, without "
             "any way back to a face.")
    visit_group_id = fields.Many2one(
        "analitix.visit.group", string="Purchase Unit", index=True,
        ondelete="set null")

    entered_at = fields.Datetime(
        string="Entered", required=True, index=True,
        default=lambda self: fields.Datetime.now())
    exited_at = fields.Datetime(string="Exited")
    duration_min = fields.Float(
        string="Duration (min)", compute="_compute_duration", store=True,
        help="Time between entering and the last exit seen. Empty while the "
             "visit is still open.")
    state = fields.Selection(
        selection=[("inside", "Inside"), ("left", "Left")],
        string="State", default="inside", required=True, index=True)

    crossing_ids = fields.One2many(
        "analitix.event", "visitor_id", string="Crossings")
    crossing_count = fields.Integer(compute="_compute_crossing_count")
    re_entry_count = fields.Integer(
        string="Re-entries", default=0,
        help="How many times this person came back in during the same visit. A "
             "high number at a single-door store usually means the virtual line "
             "sits across a waiting area rather than in the doorway.")

    demographic_id = fields.Many2one(
        "analitix.demographic", string="Profile", ondelete="set null")
    age_band = fields.Selection(
        related="demographic_id.age_band", store=True, string="Age Band")
    gender = fields.Selection(
        related="demographic_id.gender", store=True, string="Gender")

    is_returning = fields.Boolean(
        string="Returning", default=False,
        help="This person's signature already existed when they walked in — "
             "they had been in recently. Within the retention window only; the "
             "long-horizon 'how often does this customer come back' question "
             "belongs to phase 4.")

    _store_entered_idx = models.Index("(store_id, entered_at DESC)")

    # ------------------------------------------------------------------
    @api.depends("store_id", "entered_at", "signature_id")
    def _compute_display_reference(self):
        for visit in self:
            stamp = fields.Datetime.to_string(visit.entered_at or fields.Datetime.now())
            visit.display_reference = "%s / %s" % (
                visit.signature_id.reference or _("anonymous"), stamp)

    @api.depends("entered_at", "exited_at")
    def _compute_duration(self):
        for visit in self:
            if visit.entered_at and visit.exited_at:
                delta = visit.exited_at - visit.entered_at
                visit.duration_min = delta.total_seconds() / 60.0
            else:
                visit.duration_min = 0.0

    def _compute_crossing_count(self):
        data = self.env["analitix.event"]._read_group(
            [("visitor_id", "in", self.ids)],
            groupby=["visitor_id"], aggregates=["__count"])
        mapped = {visit.id: count for visit, count in data}
        for visit in self:
            visit.crossing_count = mapped.get(visit.id, 0)

    # ------------------------------------------------------------------
    # Building visits out of crossings
    # ------------------------------------------------------------------
    @api.model
    def _register_crossing(self, event, signature, is_new_signature):
        """Attach ``event`` to a visit, opening or closing one as needed.

        The rule for "is this the same visit or a new one" is a per-store gap,
        not a constant: a jewellery boutique where people browse for forty
        minutes and a convenience store where they are in and out in ninety
        seconds cannot share a threshold.
        """
        store = event.store_id
        open_visit = self.sudo().search([
            ("signature_id", "=", signature.id),
            ("state", "=", "inside"),
        ], order="entered_at desc", limit=1)

        if event.direction == "out":
            if open_visit:
                open_visit.write({
                    "exited_at": event.event_time,
                    "exit_door_id": event.door_id.id,
                    "state": "left",
                })
                return open_visit
            # An exit with no matching entry: the person was already inside when
            # the camera came up, or entered through an unmonitored door. Not an
            # error worth dropping data over, just nothing to close.
            return self.browse()

        if open_visit:
            # Already inside and coming in again: a re-entry, not a new visit.
            open_visit.write({
                "re_entry_count": open_visit.re_entry_count + 1,
            })
            return open_visit

        gap = timedelta(minutes=store.visit_gap_minutes)
        recent = self.sudo().search([
            ("signature_id", "=", signature.id),
            ("state", "=", "left"),
            ("exited_at", ">=", event.event_time - gap),
        ], order="exited_at desc", limit=1)
        if recent:
            # Left and came back inside the gap: the same visit resuming.
            recent.write({
                "state": "inside",
                "exited_at": False,
                "re_entry_count": recent.re_entry_count + 1,
            })
            return recent

        return self.sudo().create({
            "store_id": store.id,
            "door_id": event.door_id.id,
            "signature_id": signature.id,
            "entered_at": event.event_time,
            "state": "inside",
            "is_returning": not is_new_signature,
        })

    # ------------------------------------------------------------------
    @api.model
    def _cron_close_stale(self):
        """Close visits whose exit was never seen.

        Exits get missed — someone leaves in a crowd, the camera drops a frame.
        Left open, those visits stay 'inside' forever and quietly inflate the
        occupancy figure until it is nonsense. The cutoff is the store's own
        maximum plausible visit length.
        """
        now = fields.Datetime.now()
        for store in self.env["analitix.store"].sudo().search([]):
            cutoff = now - timedelta(minutes=store.max_visit_minutes)
            stale = self.sudo().search([
                ("store_id", "=", store.id),
                ("state", "=", "inside"),
                ("entered_at", "<", cutoff),
            ])
            if stale:
                # exited_at stays empty on purpose: we do not know when they
                # left, and inventing a time would put a fabricated duration
                # into the dwell statistics phase 3 is built on.
                stale.write({"state": "left"})
        return True
