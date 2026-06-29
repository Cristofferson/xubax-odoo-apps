# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class FootfallHourly(models.Model):
    """Read-only hourly aggregate: visitors (footfall) LEFT-JOINed with POS
    sales of the same company, to expose the conversion KPI in graph/pivot.

    Implemented as a PostgreSQL view so it is always live with zero crons.
    """
    _name = "xb.footfall.hourly"
    _description = "Footfall — Hourly Conversion"
    _auto = False
    _order = "hour desc"

    store_id = fields.Many2one("xb.footfall.store", string="Store", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    hour = fields.Datetime(string="Hour", readonly=True)
    visitors_in = fields.Integer(string="Visitors In", readonly=True)
    visitors_out = fields.Integer(string="Visitors Out", readonly=True)
    tickets = fields.Integer(string="POS Tickets", readonly=True)
    revenue = fields.Monetary(string="Revenue", readonly=True,
                              currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", string="Currency", readonly=True)
    conversion_rate = fields.Float(
        string="Conversion %", readonly=True,
        help="POS tickets divided by visitors entering, as a percentage.")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # The unit of analysis is the STORE. Visitors are summed across all the
        # store's entrance devices; sales are matched either by the store's POS
        # registers ('registers' mode — several registers in one shop) or by the
        # whole company ('company' mode — single-store company). Both are summed
        # per store and crossed by the hour.
        self.env.cr.execute("""
            CREATE VIEW %s AS (
                WITH store_visits AS (
                    SELECT d.store_id AS store_id,
                           date_trunc('hour', e.event_time) AS hour,
                           SUM(CASE WHEN e.direction = 'in'  THEN e.count ELSE 0 END) AS visitors_in,
                           SUM(CASE WHEN e.direction = 'out' THEN e.count ELSE 0 END) AS visitors_out
                    FROM xb_footfall_event e
                    JOIN xb_footfall_device d ON d.id = e.device_id
                    WHERE d.store_id IS NOT NULL
                    GROUP BY d.store_id, date_trunc('hour', e.event_time)
                ),
                store_sales AS (
                    -- stores matched by their specific registers
                    SELECT s.id AS store_id,
                           date_trunc('hour', o.date_order) AS hour,
                           COUNT(*) AS tickets,
                           SUM(o.amount_total) AS revenue
                    FROM xb_footfall_store s
                    JOIN xbf_store_register_rel rel ON rel.store_id = s.id
                    JOIN pos_order o ON o.config_id = rel.config_id
                    WHERE s.match_mode = 'registers'
                      AND o.state IN ('paid', 'done', 'invoiced')
                    GROUP BY s.id, date_trunc('hour', o.date_order)
                    UNION ALL
                    -- stores matched by the whole company
                    SELECT s.id AS store_id,
                           date_trunc('hour', o.date_order) AS hour,
                           COUNT(*) AS tickets,
                           SUM(o.amount_total) AS revenue
                    FROM xb_footfall_store s
                    JOIN pos_order o ON o.company_id = s.company_id
                    WHERE s.match_mode = 'company'
                      AND o.state IN ('paid', 'done', 'invoiced')
                    GROUP BY s.id, date_trunc('hour', o.date_order)
                )
                SELECT row_number() OVER () AS id,
                       COALESCE(v.store_id, s.store_id) AS store_id,
                       st.company_id AS company_id,
                       COALESCE(v.hour, s.hour) AS hour,
                       COALESCE(v.visitors_in, 0) AS visitors_in,
                       COALESCE(v.visitors_out, 0) AS visitors_out,
                       COALESCE(s.tickets, 0) AS tickets,
                       COALESCE(s.revenue, 0.0) AS revenue,
                       comp.currency_id AS currency_id,
                       CASE WHEN COALESCE(v.visitors_in, 0) > 0
                            THEN ROUND(100.0 * COALESCE(s.tickets, 0) / v.visitors_in, 2)
                            ELSE 0.0 END AS conversion_rate
                FROM store_visits v
                FULL OUTER JOIN store_sales s
                     ON v.store_id = s.store_id AND v.hour = s.hour
                LEFT JOIN xb_footfall_store st
                     ON st.id = COALESCE(v.store_id, s.store_id)
                LEFT JOIN res_company comp ON comp.id = st.company_id
            )
        """ % (self._table,))
