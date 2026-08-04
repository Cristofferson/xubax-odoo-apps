# -*- coding: utf-8 -*-
"""Unusual *behaviour* — anonymous, and deliberately not about people.

This is the one part of the addon most likely to be misunderstood, so the
boundary is worth stating plainly: **it recognises patterns, never persons.**
There is no list, no identity, no history that follows anybody out of the shop.
It reuses the same dwell-and-nudge plumbing as the lost-sale path; only the
trigger differs.

What it notices
---------------
* **In and out repeatedly** in a short span — someone checking the room.
* **A long stop at the expensive case with nobody nearby** — which is equally a
  security signal and a *sales* signal, and that ambiguity is the point.
* **A group that arrives together and immediately scatters** to separate
  corners — the classic distraction shape.
* **A visit that never closed** — somebody entered hours ago and no exit was
  ever recorded. Worth saying plainly what this usually means: not a person
  hiding behind the stock, but an exit the camera missed. Both readings deserve
  a look, and the second one is arguably the more valuable, because a visit
  that never closes inflates the occupancy figure and quietly corrupts every
  "how many are inside" number after it. It is also the one signal the other
  three structurally cannot see: they scan visits opened *recently*, and a
  visit that has been open for six hours fell out of that window five hours
  ago.

What it says
------------
"Worth going over" — the same nudge a possible lost sale produces, to the same
salesperson, through the same discreet channel. It never says anyone is a
thief, because it does not know that and neither does the shop. A salesperson
walking over is the correct response to all three signals whether the person is
a shoplifter or a customer nobody has served.

Named people with a recorded history are phase 5's watch list. That is a
different feature with different controls, and keeping them apart is
intentional: this one is safe to leave on everywhere.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AnalitixAnomalyEvent(models.Model):
    _name = "analitix.anomaly.event"
    _description = "Analitix Behaviour Signal"
    _order = "detected_at desc, id desc"
    _rec_name = "kind"

    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)
    zone_id = fields.Many2one(
        "analitix.zone", string="Zone", index=True, ondelete="set null")
    visitor_id = fields.Many2one(
        "analitix.visitor", string="Visit", index=True, ondelete="cascade",
        help="The pseudonymous visit. It expires with its signature; nothing "
             "here outlives the shop's retention window.")
    visit_group_id = fields.Many2one(
        "analitix.visit.group", string="Purchase Unit", ondelete="set null")

    kind = fields.Selection(
        selection=[
            ("repeat_entry", "In and out repeatedly"),
            ("long_unattended", "Long stop, nobody nearby"),
            ("group_dispersal", "Arrived together, scattered"),
            ("never_left", "Entered, never left"),
        ],
        string="Signal", required=True, index=True)
    detected_at = fields.Datetime(
        string="Detected", required=True, index=True,
        default=lambda self: fields.Datetime.now())
    detail = fields.Char(string="Detail")
    alert_id = fields.Many2one(
        "analitix.alert", string="Alert", ondelete="set null")
    outcome = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("nothing", "Nothing in it"),
            ("served", "Customer just needed help"),
            ("incident", "Turned out to matter"),
        ],
        string="Outcome", default="pending", index=True,
        help="Filled in afterwards by the person who went over. 'Nothing in it' "
             "and 'just needed help' are the answers we expect most of the "
             "time, and recording them is what lets a store see whether its "
             "thresholds are set sensibly.")

    _store_detected_idx = models.Index("(store_id, detected_at DESC)")

    # ------------------------------------------------------------------
    @api.model
    def _raise(self, store, kind, visitor, zone=None, detail=None, group=None):
        """Record a signal and nudge, once per visit per kind."""
        if not store.anomaly_detection_enabled:
            return self.browse()
        if visitor and self.sudo().search_count([
                ("visitor_id", "=", visitor.id), ("kind", "=", kind)]):
            return self.browse()

        summaries = {
            "repeat_entry": _("Someone has come in and out several times"),
            "long_unattended": _("Long stop at %(zone)s with nobody nearby",
                                 zone=zone.name if zone else _("a display")),
            "group_dispersal": _("A group came in together and split up"),
            "never_left": _("A visit has been open for hours with no exit"),
        }
        # The three floor signals share one closing line; "never left" does not,
        # because telling a salesperson that somebody who walked in this morning
        # "simply wants help" would be nonsense. Its likeliest explanation is a
        # missed exit, and saying so is what makes the nudge actionable.
        if kind == "never_left":
            tail = _("Either somebody is still in the shop, or the exit was "
                     "not seen — which would mean the occupancy figure is "
                     "running high. Both are worth thirty seconds.")
        else:
            tail = _("Worth going over. This is a behaviour pattern, not an "
                     "accusation — most of the time the person simply wants "
                     "help.")
        alert = self.env["analitix.alert"].raise_alert(
            store, "anomaly", summaries.get(kind, _("Worth a look")),
            body=_("%(detail)s\n\n%(tail)s",
                   detail=detail or summaries.get(kind, ""), tail=tail),
            zone=zone, visitor=visitor)

        return self.sudo().create({
            "store_id": store.id,
            "zone_id": zone.id if zone else False,
            "visitor_id": visitor.id if visitor else False,
            "visit_group_id": group.id if group else False,
            "kind": kind,
            "detail": detail,
            "alert_id": alert.id if alert else False,
        })

    # ------------------------------------------------------------------
    @api.model
    def _cron_scan(self):
        """Look over the open visits for the three shapes.

        A cron rather than an inline check on every crossing: two of the three
        signals are only visible over a window of time, and re-evaluating them
        on each event would be both wasteful and jittery.
        """
        Visitor = self.env["analitix.visitor"].sudo()
        for store in self.env["analitix.store"].sudo().search(
                [("anomaly_detection_enabled", "=", True)]):
            since = fields.Datetime.now() - timedelta(
                minutes=store.anomaly_window_minutes)
            open_visits = Visitor.search([
                ("store_id", "=", store.id),
                ("state", "=", "inside"),
                ("entered_at", ">=", since),
            ])
            for visit in open_visits:
                self._scan_visit(store, visit)
            self._scan_stale(store)
        return True

    @api.model
    def _scan_stale(self, store):
        """Visits that are still open long after anybody could still be inside.

        Deliberately a separate search from the one above: that one is bounded
        to ``anomaly_window_minutes`` so the common signals stay cheap, which
        means the visit we are looking for here — old by definition — is
        exactly the one it cannot reach.
        """
        cutoff = fields.Datetime.now() - timedelta(
            minutes=store.anomaly_never_left_minutes)
        stale = self.env["analitix.visitor"].sudo().search([
            ("store_id", "=", store.id),
            ("state", "=", "inside"),
            ("entered_at", "<", cutoff),
        ])
        for visit in stale:
            hours = (fields.Datetime.now() - visit.entered_at).total_seconds() / 3600
            self._raise(
                store, "never_left", visit,
                detail=_("Open for %(hours)s hours with no exit recorded.",
                         hours=round(hours, 1)))
        return True

    @api.model
    def _scan_visit(self, store, visit):
        # 1. In and out repeatedly.
        if visit.re_entry_count >= store.anomaly_reentry_count:
            self._raise(
                store, "repeat_entry", visit, zone=False,
                detail=_("%(n)s re-entries during one visit.",
                         n=visit.re_entry_count))

        # 2. A long stop where nobody went over. Only in zones the shop marked
        #    as worth watching — a fitting room is not one.
        long_dwells = self.env["analitix.zone.dwell"].sudo().search([
            ("visitor_id", "=", visit.id),
            ("served", "=", False),
            ("seconds", ">=", store.anomaly_dwell_seconds),
            ("zone_id.alert_on_dwell", "=", True),
        ], limit=1)
        if long_dwells:
            self._raise(
                store, "long_unattended", visit, zone=long_dwells.zone_id,
                detail=_("%(mins)s minutes at %(zone)s, unattended.",
                         mins=int(long_dwells.seconds / 60),
                         zone=long_dwells.zone_id.name))

        # 3. Arrived together, scattered. Needs a unit of at least three: two
        #    people wandering to different shelves is a couple shopping.
        group = visit.visit_group_id
        if group and group.size >= 3:
            zones = self.env["analitix.zone.dwell"].sudo()._read_group(
                [("visitor_id", "in", group.visitor_ids.ids)],
                groupby=["zone_id"], aggregates=["__count"])
            if len(zones) >= store.anomaly_dispersal_zones:
                self._raise(
                    store, "group_dispersal", visit, group=group,
                    detail=_("%(size)s people arrived together and are now in "
                             "%(zones)s different zones.",
                             size=group.size, zones=len(zones)))
        return True
