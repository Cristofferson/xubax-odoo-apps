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
    # --- Raw measures (sum correctly when grouped) ---
    visitors_in = fields.Integer(string="Visitors In", readonly=True)
    visitors_out = fields.Integer(string="Visitors Out", readonly=True)
    tickets = fields.Integer(string="POS Tickets", readonly=True)
    units = fields.Integer(
        string="Units Sold", readonly=True,
        help="Total quantity of items sold (sum of POS order line quantities).")
    revenue = fields.Monetary(string="Revenue", readonly=True,
                              currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", string="Currency", readonly=True)
    area_sqm = fields.Float(string="Store m²", readonly=True)
    # --- Ratios (per-hour values; averaged when grouped) ---
    conversion_rate = fields.Float(
        string="Conversion %", readonly=True, aggregator="avg",
        help="POS tickets divided by visitors entering, as a percentage.")
    atv = fields.Monetary(
        string="Avg Ticket (ATV)", readonly=True, currency_field="currency_id",
        aggregator="avg", help="Revenue divided by tickets: average value of a sale.")
    upt = fields.Float(
        string="Units / Ticket (UPT)", readonly=True, aggregator="avg",
        help="Units sold divided by tickets: basket size.")
    revenue_per_visitor = fields.Monetary(
        string="Revenue / Visitor", readonly=True, currency_field="currency_id",
        aggregator="avg",
        help="Revenue divided by visitors entering: the money each walk-in yields.")
    visitors_per_ticket = fields.Float(
        string="Visitors / Ticket", readonly=True, aggregator="avg",
        help="Visitors entering divided by tickets: how many people walk in per sale.")
    visitors_per_unit = fields.Float(
        string="Visitors / Unit", readonly=True, aggregator="avg",
        help="Visitors entering divided by units sold: how many people per item sold.")
    # --- Density (sum correctly: area is constant per store) ---
    revenue_per_sqm = fields.Monetary(
        string="Revenue / m²", readonly=True, currency_field="currency_id",
        help="Revenue divided by the store's total m²: sales density.")
    visitors_per_sqm = fields.Float(
        string="Visitors / m²", readonly=True,
        help="Visitors entering divided by the store's total m²: traffic density.")

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
                order_units AS (
                    -- units per order, pre-aggregated so joining lines does not
                    -- multiply the order-level revenue/ticket counts
                    SELECT l.order_id, SUM(l.qty) AS units
                    FROM pos_order_line l
                    GROUP BY l.order_id
                ),
                store_sales AS (
                    -- stores matched by their specific registers
                    SELECT s.id AS store_id,
                           date_trunc('hour', o.date_order) AS hour,
                           COUNT(*) AS tickets,
                           SUM(o.amount_total) AS revenue,
                           SUM(COALESCE(ou.units, 0)) AS units
                    FROM xb_footfall_store s
                    JOIN xbf_store_register_rel rel ON rel.store_id = s.id
                    JOIN pos_order o ON o.config_id = rel.config_id
                    LEFT JOIN order_units ou ON ou.order_id = o.id
                    WHERE s.match_mode = 'registers'
                      AND o.state IN ('paid', 'done', 'invoiced')
                    GROUP BY s.id, date_trunc('hour', o.date_order)
                    UNION ALL
                    -- stores matched by the whole company
                    SELECT s.id AS store_id,
                           date_trunc('hour', o.date_order) AS hour,
                           COUNT(*) AS tickets,
                           SUM(o.amount_total) AS revenue,
                           SUM(COALESCE(ou.units, 0)) AS units
                    FROM xb_footfall_store s
                    JOIN pos_order o ON o.company_id = s.company_id
                    LEFT JOIN order_units ou ON ou.order_id = o.id
                    WHERE s.match_mode = 'company'
                      AND o.state IN ('paid', 'done', 'invoiced')
                    GROUP BY s.id, date_trunc('hour', o.date_order)
                ),
                joined AS (
                    SELECT COALESCE(v.store_id, s.store_id) AS store_id,
                           COALESCE(v.hour, s.hour) AS hour,
                           COALESCE(v.visitors_in, 0) AS visitors_in,
                           COALESCE(v.visitors_out, 0) AS visitors_out,
                           COALESCE(s.tickets, 0) AS tickets,
                           COALESCE(s.revenue, 0.0) AS revenue,
                           COALESCE(s.units, 0) AS units
                    FROM store_visits v
                    FULL OUTER JOIN store_sales s
                         ON v.store_id = s.store_id AND v.hour = s.hour
                )
                SELECT row_number() OVER () AS id,
                       j.store_id AS store_id,
                       st.company_id AS company_id,
                       j.hour AS hour,
                       j.visitors_in AS visitors_in,
                       j.visitors_out AS visitors_out,
                       j.tickets AS tickets,
                       j.units AS units,
                       j.revenue AS revenue,
                       comp.currency_id AS currency_id,
                       COALESCE(st.area_sqm, 0.0) AS area_sqm,
                       CASE WHEN j.visitors_in > 0
                            THEN ROUND(100.0 * j.tickets / j.visitors_in, 2)
                            ELSE 0.0 END AS conversion_rate,
                       CASE WHEN j.tickets > 0
                            THEN ROUND(j.revenue / j.tickets, 2)
                            ELSE 0.0 END AS atv,
                       CASE WHEN j.tickets > 0
                            THEN ROUND(j.units::numeric / j.tickets, 2)
                            ELSE 0.0 END AS upt,
                       CASE WHEN j.visitors_in > 0
                            THEN ROUND(j.revenue / j.visitors_in, 2)
                            ELSE 0.0 END AS revenue_per_visitor,
                       CASE WHEN j.tickets > 0
                            THEN ROUND(j.visitors_in::numeric / j.tickets, 2)
                            ELSE 0.0 END AS visitors_per_ticket,
                       CASE WHEN j.units > 0
                            THEN ROUND(j.visitors_in::numeric / j.units, 2)
                            ELSE 0.0 END AS visitors_per_unit,
                       CASE WHEN COALESCE(st.area_sqm, 0) > 0
                            THEN ROUND(j.revenue / st.area_sqm::numeric, 2)
                            ELSE 0.0 END AS revenue_per_sqm,
                       CASE WHEN COALESCE(st.area_sqm, 0) > 0
                            THEN ROUND(j.visitors_in::numeric / st.area_sqm::numeric, 2)
                            ELSE 0.0 END AS visitors_per_sqm
                FROM joined j
                LEFT JOIN xb_footfall_store st ON st.id = j.store_id
                LEFT JOIN res_company comp ON comp.id = st.company_id
            )
        """ % (self._table,))
