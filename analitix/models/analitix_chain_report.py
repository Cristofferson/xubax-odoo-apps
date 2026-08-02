# -*- coding: utf-8 -*-
"""The corporate console: every branch measured with the same stick.

This is the argument that sells a chain, and it is a narrow one. A head office
already has sales per branch — that is what an ERP is for. What it has never
had is the *denominator*: how many people walked into each shop. Without it,
"Morelia sold less than Guadalajara" is a sentence with two possible meanings
and no way to choose between them.

With it, the two separate cleanly:

* fewer people came in → a location, a landlord or a marketing problem;
* the same people came in and fewer bought → a floor problem, which is the one
  head office can actually fix, and the one nobody could previously see.

So the report leads with conversion and rescue rate rather than with revenue.
Revenue ranks branches by how big they are, which everybody already knows.

Built over ``analitix.store.daily`` and not over raw events, on purpose: the
console has to keep answering after the crossing events have been pruned, and a
console that silently loses last year is worse than one that never had it.
"""
from odoo import fields, models, tools


class AnalitixChainReport(models.Model):
    _name = "analitix.chain.report"
    _description = "Analitix Chain Console"
    _auto = False
    _rec_name = "store_id"
    _order = "day desc, conversion_rate desc"

    day = fields.Date(string="Day", readonly=True)
    store_id = fields.Many2one("analitix.store", string="Store", readonly=True)
    region_id = fields.Many2one("analitix.region", string="Region", readonly=True)
    brand_id = fields.Many2one("analitix.brand", string="Chain", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Currency", readonly=True)

    visitors = fields.Integer(string="Visitors", readonly=True)
    tickets = fields.Integer(string="Sales", readonly=True)
    units = fields.Integer(string="Units", readonly=True)
    revenue = fields.Monetary(
        string="Revenue", currency_field="currency_id", readonly=True)

    conversion_rate = fields.Float(string="Conversion %", readonly=True, digits=(5, 2))
    atv = fields.Monetary(
        string="Average Ticket", currency_field="currency_id", readonly=True)
    upt = fields.Float(string="Units / Ticket", readonly=True, digits=(5, 2))
    revenue_per_visitor = fields.Monetary(
        string="Revenue / Visitor", currency_field="currency_id", readonly=True)

    lost_detected = fields.Integer(string="Walk-outs Spotted", readonly=True)
    lost_rescued = fields.Integer(string="Walk-outs Rescued", readonly=True)
    rescue_rate = fields.Float(string="Rescue %", readonly=True, digits=(5, 2))
    alerts_sent = fields.Integer(string="Alerts Sent", readonly=True)
    alerts_missed = fields.Integer(string="Alerts Missed", readonly=True)

    area_sqm = fields.Float(string="Total m²", readonly=True)
    revenue_per_sqm = fields.Monetary(
        string="Revenue / m²", currency_field="currency_id", readonly=True,
        help="The only fair way to compare a 60 m² kiosk against a 400 m² "
             "flagship. Ranking branches by revenue alone just ranks them by "
             "size, which head office already knows.")

    conversion_vs_region = fields.Float(
        string="Δ vs Region", readonly=True, digits=(5, 2),
        help="This store's conversion minus its region's average for the same "
             "day. The number a regional manager actually acts on: it removes "
             "the week, the weather and the season, which move every branch "
             "together, and leaves what is particular to this one.")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    d.id                            AS id,
                    d.day                           AS day,
                    d.store_id                      AS store_id,
                    d.region_id                     AS region_id,
                    d.brand_id                      AS brand_id,
                    d.company_id                    AS company_id,
                    c.currency_id                   AS currency_id,
                    d.visitors                      AS visitors,
                    d.tickets                       AS tickets,
                    d.units                         AS units,
                    d.revenue                       AS revenue,
                    d.conversion_rate               AS conversion_rate,
                    d.atv                           AS atv,
                    d.upt                           AS upt,
                    d.revenue_per_visitor           AS revenue_per_visitor,
                    d.lost_detected                 AS lost_detected,
                    d.lost_rescued                  AS lost_rescued,
                    d.rescue_rate                   AS rescue_rate,
                    d.alerts_sent                   AS alerts_sent,
                    d.alerts_missed                 AS alerts_missed,
                    s.area_sqm                      AS area_sqm,
                    CASE WHEN COALESCE(s.area_sqm, 0) > 0
                         THEN ROUND((d.revenue / s.area_sqm)::numeric, 2)
                         ELSE 0 END                 AS revenue_per_sqm,
                    -- The store's conversion against the average of its own
                    -- region on the SAME day. Comparing a Tuesday in Morelia
                    -- against a Saturday anywhere would measure the calendar,
                    -- not the shop.
                    CASE WHEN d.region_id IS NULL THEN 0
                         ELSE ROUND((d.conversion_rate - AVG(d.conversion_rate)
                              OVER (PARTITION BY d.region_id, d.day))::numeric, 2)
                    END                             AS conversion_vs_region
                FROM analitix_store_daily d
                JOIN analitix_store s   ON s.id = d.store_id
                JOIN res_company c      ON c.id = d.company_id
            )
        """ % self._table)
