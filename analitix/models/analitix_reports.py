# -*- coding: utf-8 -*-
"""Two read-only views the owner actually asks for.

``analitix.coaching.report``
    Per salesperson: how many nudges they got, how fast they answered, and how
    many of the ones they answered ended in a sale. Written to be *usable as
    coaching* rather than as a stick — which is why it counts what somebody did
    with the alerts they received, and never ranks people on traffic they never
    saw.

``analitix.recurrence.report``
    How often people come back. The signature that made it possible has usually
    been deleted by then; what survives is the visit, which is all this needs.
"""
from odoo import fields, models, tools


class AnalitixCoachingReport(models.Model):
    _name = "analitix.coaching.report"
    _description = "Analitix — Floor Coaching"
    _auto = False
    _order = "day desc, alerts desc"

    user_id = fields.Many2one("res.users", string="Salesperson", readonly=True)
    store_id = fields.Many2one("analitix.store", string="Store", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    zone_id = fields.Many2one("analitix.zone", string="Zone", readonly=True)
    day = fields.Date(string="Day", readonly=True)

    alerts = fields.Integer(string="Alerts", readonly=True)
    acknowledged = fields.Integer(string="Answered", readonly=True)
    missed = fields.Integer(string="Missed", readonly=True)
    sold = fields.Integer(string="Ended In A Sale", readonly=True)
    avg_response_seconds = fields.Float(
        string="Avg Response (s)", readonly=True, aggregator="avg")
    answer_rate = fields.Float(
        string="Answered %", readonly=True, aggregator="avg")
    conversion_rate = fields.Float(
        string="Converted %", readonly=True, aggregator="avg",
        help="Of the alerts this person answered, how many ended in a sale. "
             "Measured against what they answered rather than what they were "
             "sent, because nobody should be marked down for a nudge that "
             "arrived while they were with another customer.")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW %s AS (
                SELECT row_number() OVER (
                           ORDER BY a.user_id, a.store_id, a.zone_id,
                                    (a.sent_at AT TIME ZONE 'UTC')::date) AS id,
                       a.user_id,
                       a.store_id,
                       a.zone_id,
                       s.company_id,
                       (a.sent_at AT TIME ZONE 'UTC')::date AS day,
                       COUNT(*) AS alerts,
                       SUM(CASE WHEN a.acknowledged THEN 1 ELSE 0 END) AS acknowledged,
                       SUM(CASE WHEN a.outcome = 'missed' THEN 1 ELSE 0 END) AS missed,
                       SUM(CASE WHEN a.outcome = 'sold' THEN 1 ELSE 0 END) AS sold,
                       COALESCE(AVG(NULLIF(a.response_seconds, 0)), 0)
                           AS avg_response_seconds,
                       CASE WHEN COUNT(*) > 0
                            THEN ROUND(100.0
                                 * SUM(CASE WHEN a.acknowledged THEN 1 ELSE 0 END)
                                 / COUNT(*), 2)
                            ELSE 0.0 END AS answer_rate,
                       CASE WHEN SUM(CASE WHEN a.acknowledged THEN 1 ELSE 0 END) > 0
                            THEN ROUND(100.0
                                 * SUM(CASE WHEN a.outcome = 'sold' THEN 1 ELSE 0 END)
                                 / SUM(CASE WHEN a.acknowledged THEN 1 ELSE 0 END), 2)
                            ELSE 0.0 END AS conversion_rate
                FROM analitix_alert a
                JOIN analitix_store s ON s.id = a.store_id
                WHERE a.user_id IS NOT NULL
                GROUP BY a.user_id, a.store_id, a.zone_id, s.company_id,
                         (a.sent_at AT TIME ZONE 'UTC')::date
            )
        """ % (self._table,))


class AnalitixRecurrenceReport(models.Model):
    _name = "analitix.recurrence.report"
    _description = "Analitix — Visit Frequency"
    _auto = False
    _order = "day desc"

    store_id = fields.Many2one("analitix.store", string="Store", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    day = fields.Date(string="Day", readonly=True)
    visits = fields.Integer(string="Visits", readonly=True)
    returning_visits = fields.Integer(string="Returning", readonly=True)
    identified_visits = fields.Integer(string="Known Customers", readonly=True)
    return_rate = fields.Float(
        string="Returning %", readonly=True, aggregator="avg",
        help="Share of the day's visits made by somebody the store had seen "
             "before, within its own retention window. A short window makes "
             "this number smaller — it measures what the store chose to "
             "remember, not everything that happened.")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW %s AS (
                SELECT row_number() OVER (
                           ORDER BY v.store_id,
                                    (v.entered_at AT TIME ZONE 'UTC')::date) AS id,
                       v.store_id,
                       s.company_id,
                       (v.entered_at AT TIME ZONE 'UTC')::date AS day,
                       COUNT(*) AS visits,
                       SUM(CASE WHEN v.is_returning THEN 1 ELSE 0 END)
                           AS returning_visits,
                       SUM(CASE WHEN sig.identified THEN 1 ELSE 0 END)
                           AS identified_visits,
                       CASE WHEN COUNT(*) > 0
                            THEN ROUND(100.0
                                 * SUM(CASE WHEN v.is_returning THEN 1 ELSE 0 END)
                                 / COUNT(*), 2)
                            ELSE 0.0 END AS return_rate
                FROM analitix_visitor v
                JOIN analitix_store s ON s.id = v.store_id
                LEFT JOIN analitix_face_signature sig ON sig.id = v.signature_id
                GROUP BY v.store_id, s.company_id,
                         (v.entered_at AT TIME ZONE 'UTC')::date
            )
        """ % (self._table,))
