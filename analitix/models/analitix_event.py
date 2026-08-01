# -*- coding: utf-8 -*-
"""A crossing: one person passing a door's virtual line, in or out.

This is the highest-volume table in the addon — a busy store produces thousands
of rows a day and a chain produces millions — so it stays deliberately narrow
and heavily indexed, and every aggregate reads from it rather than storing a
second copy of the truth.

Idempotency (task 982, point 2)
-------------------------------
The edge generates a ``uuid`` per crossing *before* it tries to send it, and
keeps retrying until Odoo acknowledges.  A unique index on that uuid is what
makes the retry safe: a flaky store link can replay the same batch five times
and the person is still counted once.  Without it, the customer's conversion
rate would quietly improve every time their internet hiccuped.
"""
from datetime import timedelta

from odoo import api, fields, models


class AnalitixEvent(models.Model):
    _name = "analitix.event"
    _description = "Analitix Crossing Event"
    _order = "event_time desc, id desc"
    _rec_name = "event_time"

    uuid = fields.Char(
        string="Event UUID", required=True, index=True, copy=False, readonly=True,
        help="Unique identifier minted by the edge agent before sending. It is "
             "what makes a network retry safe: the same crossing arriving twice "
             "is stored once.")
    device_id = fields.Many2one(
        "analitix.device", string="Device", required=True, index=True,
        ondelete="cascade")
    door_id = fields.Many2one(
        "analitix.door", string="Door", index=True, ondelete="set null")
    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)

    event_time = fields.Datetime(
        string="Time", required=True, index=True,
        default=lambda self: fields.Datetime.now(),
        help="When the crossing happened at the store, as reported by the edge "
             "— not when Odoo received it. After an outage a device replays "
             "hours of buffered events, and they must land on the hour they "
             "actually belong to or the day's curve is wrong.")
    received_at = fields.Datetime(
        string="Received", readonly=True, default=lambda self: fields.Datetime.now(),
        help="When Odoo stored it. Compared against 'Time' it shows how far "
             "behind a store's link is running.")
    direction = fields.Selection(
        selection=[("in", "Entrance"), ("out", "Exit")],
        string="Direction", required=True, default="in", index=True)
    count = fields.Integer(string="People", default=1)

    # --- staff exclusion (phase 1, point 6) ---
    counted = fields.Boolean(
        string="Counts As Visitor", default=True, index=True,
        help="Cleared when the crossing was matched to an employee, or when it "
             "came through a door configured not to count visitors. The row is "
             "kept either way — excluded traffic is still traffic, and hiding "
             "it would make an audit impossible.")
    staff_id = fields.Many2one(
        "hr.employee", string="Employee", index=True, ondelete="set null",
        help="Set when this crossing was attributed to a known employee.")
    match_score = fields.Float(
        string="Match Score", digits=(3, 3),
        help="Cosine similarity of the staff match, kept so a threshold can be "
             "re-tuned against real data instead of guesswork.")

    # --- hooks for the later phases ---
    track_ref = fields.Char(
        string="Edge Track", index=True,
        help="The tracker id the edge assigned to this person while they were "
             "in frame. Phase 2 uses it to tie the crossing to a visitor.")
    pending_embedding = fields.Text(
        string="Pending Embedding", copy=False, groups="analitix.group_manager",
        help="Encrypted embedding awaiting asynchronous matching. Cleared once "
             "the job has run, so the high-volume table does not become a "
             "biometric store.")

    _uuid_uniq = models.Constraint(
        "unique(uuid)", "This event was already received (duplicate UUID).")
    _count_positive = models.Constraint(
        "CHECK(count > 0)", "A crossing must involve at least one person.")

    # Composite indexes for the two queries that actually run hot. Odoo's
    # per-column indexes do not serve the range scans the dashboards issue —
    # always *store plus time window*, usually *counted only* — and at chain
    # volume the difference is a sequential scan over millions of rows on every
    # dashboard refresh.
    _store_time_idx = models.Index("(store_id, event_time DESC)")
    _store_counted_time_idx = models.Index(
        "(store_id, counted, direction, event_time)")
    _door_time_idx = models.Index("(door_id, event_time DESC)")

    @api.model
    def _cron_apply_retention(self):
        """Delete crossings older than the configured retention window.

        Off by default (``analitix.event_retention_days = 0``) because the
        hourly views read straight from this table: pruning here shortens the
        history every dashboard and year-on-year comparison can reach. It
        exists so a customer whose data policy says "ninety days" can hold to
        it, and it is their policy that sets the number, not us.
        """
        days = int(self.env["ir.config_parameter"].sudo().get_param(
            "analitix.event_retention_days", "0") or 0)
        if days <= 0:
            return True
        cutoff = fields.Datetime.now() - timedelta(days=days)
        # Chunked: a year of chain traffic is millions of rows, and handing
        # PostgreSQL one unbounded DELETE would build a lock set big enough to
        # stall live ingest while it runs.
        while True:
            batch = self.sudo().search([("event_time", "<", cutoff)], limit=5000)
            if not batch:
                break
            batch.unlink()
        return True

    @api.model
    def existing_uuids(self, uuids):
        """Return the subset of ``uuids`` already stored.

        One query for a whole batch: the ingest controller filters duplicates
        up front instead of catching a unique-violation per row, which would
        abort the enclosing transaction and lose the good events with it.
        """
        if not uuids:
            return set()
        rows = self.sudo().search_read(
            [("uuid", "in", list(uuids))], ["uuid"], load=False)
        return {row["uuid"] for row in rows}
