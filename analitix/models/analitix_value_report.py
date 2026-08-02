# -*- coding: utf-8 -*-
"""The monthly value report — the argument that renews the subscription.

The brief calls this the piece that sustains the rent, and it is right. A shop
owner does not renew because a dashboard exists; they renew because once a month
something arrives that says, in their language and without them interpreting
anything: *this many people came in, this many bought, we spotted this many
people about to walk out unserved, your team caught this many of them, and that
was worth roughly this much.*

Two rules govern how it is written
----------------------------------
**Business language, not ours.** No "conversion rate delta", no model names. If
a sentence needs the reader to know what Analitix calls something, it is
rewritten.

**Never overclaim.** Recovered revenue is an *estimate* built from the store's
own average ticket, and it says so every time it appears. A rescued sale is one
where an alert fired and that same visit produced a ticket afterwards — which is
correlation, honestly labelled, not proof that the nudge caused the sale.
Inflating this number is the fastest way to lose the customer who eventually
checks it, and the whole product rests on the owner trusting these figures.
"""
import logging
from datetime import date, timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AnalitixValueReport(models.Model):
    _name = "analitix.value.report"
    _description = "Analitix Monthly Value Report"
    _order = "period_start desc, store_id"
    _rec_name = "display_name"

    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True)

    period_start = fields.Date(string="From", required=True, index=True)
    period_end = fields.Date(string="To", required=True)

    # --- what happened ---
    visitors = fields.Integer(string="Visitors")
    tickets = fields.Integer(string="Sales")
    revenue = fields.Monetary(string="Revenue", currency_field="currency_id")
    conversion_rate = fields.Float(string="Conversion %", aggregator="avg")
    average_ticket = fields.Monetary(
        string="Average Sale", currency_field="currency_id", aggregator="avg")

    # --- what the system did about it ---
    alerts_sent = fields.Integer(string="Alerts Sent")
    alerts_acknowledged = fields.Integer(string="Alerts Acted On")
    alerts_missed = fields.Integer(string="Alerts Missed")
    lost_sales_detected = fields.Integer(string="Walk-outs Spotted")
    lost_sales_rescued = fields.Integer(string="Walk-outs Rescued")
    rescue_rate = fields.Float(string="Rescue %", aggregator="avg")
    estimated_recovered = fields.Monetary(
        string="Estimated Recovered", currency_field="currency_id",
        help="Rescued walk-outs times the store's own average sale. An "
             "estimate, labelled as one everywhere it appears: a rescued sale "
             "is one where an alert fired and that visit later produced a "
             "ticket — correlation, honestly stated, not proof.")
    monthly_fee = fields.Monetary(
        string="Subscription", currency_field="currency_id")
    times_fee = fields.Float(
        string="× Subscription",
        help="Estimated recovered revenue against what the store paid. The "
             "single number the owner is actually asking about.")

    # --- comparison ---
    prev_conversion_rate = fields.Float(string="Previous Conversion %", aggregator="avg")
    conversion_delta = fields.Float(string="Change")

    sent_on = fields.Datetime(string="Sent", readonly=True)
    state = fields.Selection(
        selection=[("draft", "Draft"), ("sent", "Sent")],
        default="draft", required=True, index=True)

    _store_period_uniq = models.Constraint(
        "unique(store_id, period_start)",
        "This store already has a report for that month.")

    @api.depends("store_id", "period_start")
    def _compute_display_name(self):
        for report in self:
            report.display_name = "%s · %s" % (
                report.store_id.name or "", report.period_start or "")

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------
    @api.model
    def build(self, store, period_start, period_end):
        """Compute (or recompute) one store's report for one month."""
        start_dt = fields.Datetime.to_datetime(period_start)
        end_dt = fields.Datetime.to_datetime(period_end) + timedelta(days=1)

        rows = self.env["analitix.hourly"].sudo().search([
            ("store_id", "=", store.id),
            ("hour", ">=", start_dt), ("hour", "<", end_dt),
        ])
        visitors = sum(rows.mapped("visitors_in"))
        tickets = sum(rows.mapped("tickets"))
        revenue = sum(rows.mapped("revenue"))
        conversion = (100.0 * tickets / visitors) if visitors else 0.0
        average = (revenue / tickets) if tickets else 0.0

        Alert = self.env["analitix.alert"].sudo()
        alert_domain = [
            ("store_id", "=", store.id),
            ("sent_at", ">=", start_dt), ("sent_at", "<", end_dt),
        ]
        alerts_sent = Alert.search_count(alert_domain)
        acknowledged = Alert.search_count(
            alert_domain + [("acknowledged", "=", True)])
        missed = Alert.search_count(alert_domain + [("outcome", "=", "missed")])

        Lost = self.env["analitix.lost.sale"].sudo()
        lost_domain = [
            ("store_id", "=", store.id),
            ("detected_at", ">=", start_dt), ("detected_at", "<", end_dt),
        ]
        detected = Lost.search_count(lost_domain)
        rescued = Lost.search_count(lost_domain + [("state", "=", "rescued")])
        rescue_rate = (100.0 * rescued / detected) if detected else 0.0
        recovered = rescued * average

        previous = self._previous_conversion(store, period_start)

        vals = {
            "store_id": store.id,
            "period_start": period_start,
            "period_end": period_end,
            "visitors": visitors,
            "tickets": tickets,
            "revenue": revenue,
            "conversion_rate": round(conversion, 2),
            "average_ticket": average,
            "alerts_sent": alerts_sent,
            "alerts_acknowledged": acknowledged,
            "alerts_missed": missed,
            "lost_sales_detected": detected,
            "lost_sales_rescued": rescued,
            "rescue_rate": round(rescue_rate, 2),
            "estimated_recovered": recovered,
            "monthly_fee": store.monthly_fee,
            "times_fee": (recovered / store.monthly_fee)
                         if store.monthly_fee else 0.0,
            "prev_conversion_rate": previous,
            "conversion_delta": round(conversion - previous, 2),
        }
        existing = self.sudo().search([
            ("store_id", "=", store.id), ("period_start", "=", period_start),
        ], limit=1)
        if existing:
            existing.write(vals)
            return existing
        return self.sudo().create(vals)

    @api.model
    def _previous_conversion(self, store, period_start):
        """Last month's figure, so the report can say better or worse."""
        previous = self.sudo().search([
            ("store_id", "=", store.id),
            ("period_start", "<", period_start),
        ], order="period_start desc", limit=1)
        return previous.conversion_rate if previous else 0.0

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def action_send(self):
        """Mail it to the store's owner."""
        template = self.env.ref(
            "analitix.mail_template_value_report", raise_if_not_found=False)
        for report in self:
            recipients = report.store_id.report_partner_ids
            if not template or not recipients:
                _logger.info(
                    "Analitix: no recipients for the value report of %s.",
                    report.store_id.display_name)
                continue
            template.with_context(
                report_partner_ids=recipients.ids
            ).send_mail(report.id, force_send=False)
            report.write({
                "state": "sent", "sent_on": fields.Datetime.now()})
        return True

    @api.model
    def _cron_monthly(self):
        """Build and send last month's report for every live store."""
        today = fields.Date.context_today(self)
        first_of_this = today.replace(day=1)
        period_end = first_of_this - timedelta(days=1)
        period_start = period_end.replace(day=1)

        stores = self.env["analitix.store"].sudo().search([
            ("value_report_enabled", "=", True),
            ("subscription_state", "in", ("trial", "active")),
        ])
        for store in stores:
            try:
                report = self.build(store, period_start, period_end)
                if report.state == "draft":
                    report.action_send()
            except Exception:  # noqa: BLE001
                # One store's bad month must not stop the other forty from
                # getting their report.
                _logger.exception(
                    "Analitix: could not build the value report for store %s.",
                    store.id)
        return True

    # ------------------------------------------------------------------
    def summary_lines(self):
        """The report as plain sentences, for the e-mail body.

        Assembled here rather than in QWeb so the wording is testable and lives
        next to the numbers it describes.
        """
        self.ensure_one()
        currency = self.currency_id.symbol or ""
        lines = [
            _("%(visitors)s people came into the shop.", visitors=self.visitors),
            _("%(tickets)s of them bought something — that is %(rate).1f%% of "
              "everyone who walked in.",
              tickets=self.tickets, rate=self.conversion_rate),
        ]
        if self.prev_conversion_rate:
            if self.conversion_delta > 0:
                lines.append(_(
                    "That is better than last month (%(prev).1f%%).",
                    prev=self.prev_conversion_rate))
            elif self.conversion_delta < 0:
                lines.append(_(
                    "That is down from last month (%(prev).1f%%).",
                    prev=self.prev_conversion_rate))
        if self.lost_sales_detected:
            lines.append(_(
                "We spotted %(detected)s people who were about to leave without "
                "being served. Your team got to %(rescued)s of them, and those "
                "visits ended in a sale.",
                detected=self.lost_sales_detected,
                rescued=self.lost_sales_rescued))
            lines.append(_(
                "At your average sale of %(cur)s%(avg).2f, that is roughly "
                "%(cur)s%(recovered).2f you would probably not have taken. "
                "It is an estimate, not a measurement.",
                cur=currency, avg=self.average_ticket,
                recovered=self.estimated_recovered))
        if self.alerts_missed:
            lines.append(_(
                "%(missed)s alerts went unanswered. Each one was somebody "
                "waiting.", missed=self.alerts_missed))
        return lines
