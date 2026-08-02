# -*- coding: utf-8 -*-
"""The daily rollup, and why a chain cannot report off raw events.

``analitix.hourly`` is a SQL view over ``analitix_event``. That is exactly right
for one shop looking at last week: the table is small, the view is always
current, and there is nothing to maintain.

It stops being right at chain scale, for two reasons that compound:

* **Volume.** A single door does roughly ten thousand crossings a month. Two
  hundred branches with two doors each is four million rows a month, and a
  head-office pivot over three years would scan a hundred and fifty million to
  answer "which branch converts worst" — a question whose answer is a few
  thousand numbers.

* **Retention.** Crossing events are the raw material recognition ran on. A
  chain that wants three years of *trend* does not need three years of *events*,
  and keeping them because the reports happen to read them is how a counting
  system quietly becomes a surveillance archive.

So this is a real table, not a view: written once a night per store per day,
and it is what the corporate console reads. Raw events then become prunable
(``prune_events``, reached from the existing retention cron) without losing a
single figure anybody looks at — which is the whole point. The rollup has to
exist *before* pruning is safe, and both the cron schedule and a per-day check
enforce that.

Idempotent by ``(store_id, day)``: re-running the rollup for a day that has
already been closed overwrites it rather than doubling it, so a cron that fires
twice after a restart is harmless.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

#: Extra days left alone behind the last rolled-up day. The rollup itself
#: re-closes a short trailing window for figures that arrive late, so pruning
#: right up to its edge would delete events that a re-close still needs.
PRUNE_SAFETY_DAYS = 2


class AnalitixStoreDaily(models.Model):
    _name = "analitix.store.daily"
    _description = "Analitix Daily Store Rollup"
    _order = "day desc, store_id"
    _rec_name = "day"

    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    region_id = fields.Many2one(
        "analitix.region", related="store_id.region_id", store=True, index=True,
        readonly=True)
    brand_id = fields.Many2one(
        "analitix.brand", related="store_id.brand_id", store=True, index=True,
        readonly=True)
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True)

    day = fields.Date(string="Day", required=True, index=True)

    visitors = fields.Integer(string="Visitors")
    tickets = fields.Integer(string="Sales")
    units = fields.Integer(string="Units")
    revenue = fields.Monetary(string="Revenue", currency_field="currency_id")
    staff_crossings = fields.Integer(string="Staff Crossings")

    lost_detected = fields.Integer(string="Walk-outs Spotted")
    lost_rescued = fields.Integer(string="Walk-outs Rescued")
    alerts_sent = fields.Integer(string="Alerts Sent")
    alerts_missed = fields.Integer(string="Alerts Missed")

#: A ratio summed across rows is nonsense — grouping a week of daily
#: conversion rates by region produced "750%". Every ratio here carries
#: aggregator="avg", the same as the hourly views have since phase 1;
#: the phase 7 models were the ones that forgot.
    conversion_rate = fields.Float(
        string="Conversion %", compute="_compute_ratios", store=True,
        digits=(5, 2), aggregator="avg")
    atv = fields.Monetary(
        string="Average Ticket", compute="_compute_ratios", store=True,
        currency_field="currency_id", aggregator="avg")
    upt = fields.Float(
        string="Units / Ticket", compute="_compute_ratios", store=True,
        digits=(5, 2), aggregator="avg")
    revenue_per_visitor = fields.Monetary(
        string="Revenue / Visitor", compute="_compute_ratios", store=True,
        currency_field="currency_id", aggregator="avg")
    rescue_rate = fields.Float(
        string="Rescue %", compute="_compute_ratios", store=True,
        digits=(5, 2), aggregator="avg",
        help="Of the walk-outs spotted, how many the team reached in time. The "
             "figure that separates a store with a traffic problem from one "
             "with a floor problem.")

    _store_day_uniq = models.Constraint(
        "unique(store_id, day)",
        "There is already a rollup for that store and day.")
    _brand_day_idx = models.Index("(brand_id, day DESC)")
    _region_day_idx = models.Index("(region_id, day DESC)")

    @api.depends("visitors", "tickets", "units", "revenue",
                 "lost_detected", "lost_rescued")
    def _compute_ratios(self):
        for row in self:
            row.conversion_rate = (
                100.0 * row.tickets / row.visitors) if row.visitors else 0.0
            row.atv = (row.revenue / row.tickets) if row.tickets else 0.0
            row.upt = (row.units / row.tickets) if row.tickets else 0.0
            row.revenue_per_visitor = (
                row.revenue / row.visitors) if row.visitors else 0.0
            row.rescue_rate = (
                100.0 * row.lost_rescued / row.lost_detected
            ) if row.lost_detected else 0.0

    # ------------------------------------------------------------------
    # Building it
    # ------------------------------------------------------------------
    @api.model
    def roll_up(self, stores, day):
        """(Re)build one day for a set of stores. Safe to run again."""
        Hourly = self.env["analitix.hourly"].sudo()
        Lost = self.env["analitix.lost.sale"].sudo()
        Alert = self.env["analitix.alert"].sudo()
        self.env.flush_all()

        for store in stores:
            # Day boundaries in the STORE's timezone, not the server's. A chain
            # spanning two timezones reporting on UTC days would compare two
            # different things and call it a comparison.
            start, end = store._day_bounds(day)

            rows = Hourly.search([
                ("store_id", "=", store.id),
                ("hour", ">=", start), ("hour", "<", end),
            ])
            lost_domain = [("store_id", "=", store.id),
                           ("detected_at", ">=", start), ("detected_at", "<", end)]
            alert_domain = [("store_id", "=", store.id),
                            ("sent_at", ">=", start), ("sent_at", "<", end)]

            vals = {
                "store_id": store.id,
                "day": day,
                "visitors": sum(rows.mapped("visitors_in")),
                "tickets": sum(rows.mapped("tickets")),
                "units": sum(rows.mapped("units")),
                "revenue": sum(rows.mapped("revenue")),
                "staff_crossings": sum(rows.mapped("staff_crossings")),
                "lost_detected": Lost.search_count(lost_domain),
                "lost_rescued": Lost.search_count(
                    lost_domain + [("state", "=", "rescued")]),
                "alerts_sent": Alert.search_count(alert_domain),
                "alerts_missed": Alert.search_count(
                    alert_domain + [("outcome", "=", "missed")]),
            }
            existing = self.sudo().search(
                [("store_id", "=", store.id), ("day", "=", day)], limit=1)
            if existing:
                existing.write(vals)
            else:
                self.sudo().create(vals)
        return True

    @api.model
    def _cron_roll_up(self, days=3):
        """Close the last few days, not just yesterday.

        A ticket can be entered late, a queued job can land after midnight, and
        a server can be down for a day. Re-closing a short window costs almost
        nothing and means a figure that arrives late still reaches the report,
        instead of leaving a hole nobody notices until a regional manager asks
        why one branch had no sales on a Tuesday.
        """
        stores = self.env["analitix.store"].sudo().search([])
        if not stores:
            return True
        today = fields.Date.context_today(self)
        for offset in range(days, 0, -1):
            self.roll_up(stores, fields.Date.subtract(today, days=offset))
        return True

    # ------------------------------------------------------------------
    # Pruning the raw events
    # ------------------------------------------------------------------
    @api.model
    def prune_events(self, batch=20000):
        """Delete crossing events older than the retention window.

        One pruning path for the whole addon, reached from
        ``analitix.event._cron_apply_retention`` so the existing scheduled
        action keeps working. Two mechanisms deleting the same table with
        different guards is how a customer eventually loses a year of history
        to whichever one had the weaker check.

        Two guards, and both earn their place:

        * **Off unless asked.** ``analitix.event_retention_days`` ships as 0.
          Turning pruning on by default at upgrade time would delete data a
          customer never agreed to lose, which is not a decision an upgrade
          gets to make.
        * **Never ahead of the rollup.** A day is only prunable once it has a
          rollup row, so pruning can never destroy figures that were never
          summarised. This is what makes retention *safe* to switch on, and it
          is the point of the daily table existing at all.

        Deleting in batches keeps the transaction short: one unbounded DELETE
        over a chain's history holds a lock long enough to stall every store
        still posting crossings.
        """
        param = self.env["ir.config_parameter"].sudo()
        days = int(param.get_param("analitix.event_retention_days", "0") or 0)
        if days <= 0:
            return True
        cutoff = fields.Date.subtract(fields.Date.context_today(self), days=days)

        Event = self.env["analitix.event"].sudo()
        total = 0
        for store in self.env["analitix.store"].sudo().search([]):
            covered = self.sudo().search([
                ("store_id", "=", store.id), ("day", "<=", cutoff),
            ], order="day desc", limit=1)
            if not covered:
                _logger.info(
                    "Analitix: nothing rolled up for %s before %s, so nothing "
                    "is pruned there — the summary has to exist first.",
                    store.display_name, cutoff)
                continue
            safe_until = fields.Date.subtract(covered.day, days=PRUNE_SAFETY_DAYS)
            start, _end = store._day_bounds(safe_until)
            while True:
                stale = Event.search(
                    [("store_id", "=", store.id), ("event_time", "<", start)],
                    limit=batch)
                if not stale:
                    break
                total += len(stale)
                stale.unlink()
        if total:
            _logger.info(
                "Analitix: pruned %d crossing event(s) older than %s. Every "
                "reported figure survives in the daily rollups.", total, cutoff)
        return True
