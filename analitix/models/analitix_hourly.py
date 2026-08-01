# -*- coding: utf-8 -*-
"""The numbers the owner actually buys.

Two read-only PostgreSQL views, both live — no cron, no stored aggregate that
can drift out of step with the events behind it:

``analitix.hourly``
    One row per **store** per hour. Visitors are summed across every door;
    tickets, revenue and units come from POS. This is where conversion lives,
    and it is at store level on purpose: a ticket belongs to the store, not to
    whichever door the customer happened to walk through, so per-door
    conversion would be a fiction.

``analitix.door.hourly``
    One row per **door** per hour: traffic only, plus each door's share of the
    store's total. This is the per-door breakdown the master instruction asks
    for — honest about what a door can and cannot tell you.

Only crossings with ``counted = true`` become visitors, which is what keeps
staff out of the denominator of every ratio on this page.
"""
from odoo import fields, models, tools


class AnalitixHourly(models.Model):
    _name = "analitix.hourly"
    _description = "Analitix — Hourly Store Conversion"
    _auto = False
    _order = "hour desc"

    store_id = fields.Many2one("analitix.store", string="Store", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    hour = fields.Datetime(string="Hour", readonly=True)

    # --- raw measures: these sum correctly when grouped ---
    visitors_in = fields.Integer(string="Visitors In", readonly=True)
    visitors_out = fields.Integer(string="Visitors Out", readonly=True)
    staff_crossings = fields.Integer(
        string="Staff Crossings", readonly=True,
        help="Employee crossings that were identified and kept out of the "
             "visitor count. Shown so the exclusion is auditable rather than "
             "invisible.")
    tickets = fields.Integer(string="POS Tickets", readonly=True)
    units = fields.Integer(string="Units Sold", readonly=True)
    revenue = fields.Monetary(
        string="Revenue", readonly=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", readonly=True)
    area_sqm = fields.Float(string="Store m²", readonly=True)

    # --- ratios: per-hour values, averaged when grouped ---
    conversion_rate = fields.Float(
        string="Conversion %", readonly=True, aggregator="avg",
        help="Tickets divided by visitors entering. The headline number: out of "
             "everyone who walked in, how many bought.")
    atv = fields.Monetary(
        string="Avg Ticket (ATV)", readonly=True, currency_field="currency_id",
        aggregator="avg", help="Revenue per ticket: what an average sale is worth.")
    upt = fields.Float(
        string="Units / Ticket (UPT)", readonly=True, aggregator="avg",
        help="Units per ticket: basket size.")
    revenue_per_visitor = fields.Monetary(
        string="Revenue / Visitor", readonly=True, currency_field="currency_id",
        aggregator="avg",
        help="Revenue divided by visitors: what each walk-in is worth. Moves "
             "when either conversion or ticket value moves, so it is the single "
             "number to watch if you only watch one.")
    visitors_per_ticket = fields.Float(
        string="Visitors / Ticket", readonly=True, aggregator="avg")
    visitors_per_unit = fields.Float(
        string="Visitors / Unit", readonly=True, aggregator="avg")

    # --- density ---
    revenue_per_sqm = fields.Monetary(
        string="Revenue / m²", readonly=True, currency_field="currency_id")
    visitors_per_sqm = fields.Float(string="Visitors / m²", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW %s AS (
                WITH store_visits AS (
                    SELECT e.store_id,
                           date_trunc('hour', e.event_time) AS hour,
                           SUM(CASE WHEN e.direction = 'in'  AND e.counted
                                    THEN e.count ELSE 0 END) AS visitors_in,
                           SUM(CASE WHEN e.direction = 'out' AND e.counted
                                    THEN e.count ELSE 0 END) AS visitors_out,
                           SUM(CASE WHEN NOT e.counted
                                    THEN e.count ELSE 0 END) AS staff_crossings
                    FROM analitix_event e
                    GROUP BY e.store_id, date_trunc('hour', e.event_time)
                ),
                order_units AS (
                    -- Pre-aggregated per order: joining lines directly would
                    -- multiply each order's revenue by its number of lines.
                    SELECT l.order_id, SUM(l.qty) AS units
                    FROM pos_order_line l
                    GROUP BY l.order_id
                ),
                store_sales AS (
                    SELECT s.id AS store_id,
                           date_trunc('hour', o.date_order) AS hour,
                           COUNT(*) AS tickets,
                           SUM(o.amount_total) AS revenue,
                           SUM(COALESCE(ou.units, 0)) AS units
                    FROM analitix_store s
                    JOIN analitix_store_register_rel rel ON rel.store_id = s.id
                    JOIN pos_order o ON o.config_id = rel.config_id
                    LEFT JOIN order_units ou ON ou.order_id = o.id
                    WHERE s.match_mode = 'registers'
                      AND o.state IN ('paid', 'done', 'invoiced')
                    GROUP BY s.id, date_trunc('hour', o.date_order)
                    UNION ALL
                    SELECT s.id AS store_id,
                           date_trunc('hour', o.date_order) AS hour,
                           COUNT(*) AS tickets,
                           SUM(o.amount_total) AS revenue,
                           SUM(COALESCE(ou.units, 0)) AS units
                    FROM analitix_store s
                    JOIN pos_order o ON o.company_id = s.company_id
                    LEFT JOIN order_units ou ON ou.order_id = o.id
                    WHERE s.match_mode = 'company'
                      AND o.state IN ('paid', 'done', 'invoiced')
                    GROUP BY s.id, date_trunc('hour', o.date_order)
                ),
                joined AS (
                    -- FULL OUTER JOIN, not LEFT: an hour with sales but no
                    -- visitors means the counter was down, and hiding it would
                    -- make a broken camera look like a quiet morning.
                    SELECT COALESCE(v.store_id, s.store_id) AS store_id,
                           COALESCE(v.hour, s.hour) AS hour,
                           COALESCE(v.visitors_in, 0) AS visitors_in,
                           COALESCE(v.visitors_out, 0) AS visitors_out,
                           COALESCE(v.staff_crossings, 0) AS staff_crossings,
                           COALESCE(s.tickets, 0) AS tickets,
                           COALESCE(s.revenue, 0.0) AS revenue,
                           COALESCE(s.units, 0) AS units
                    FROM store_visits v
                    FULL OUTER JOIN store_sales s
                         ON v.store_id = s.store_id AND v.hour = s.hour
                )
                -- ORDER BY in the window is not cosmetic: a bare
                -- row_number() OVER () renumbers the rows on every execution,
                -- so the ORM's search (which collects ids) and its follow-up
                -- read (which fetches those ids) can land on different rows and
                -- report one store's traffic under another's name. Ordering by
                -- the view's natural key makes the id a stable function of
                -- (store, hour).
                SELECT row_number() OVER (ORDER BY j.store_id, j.hour) AS id,
                       j.store_id,
                       st.company_id,
                       j.hour,
                       j.visitors_in,
                       j.visitors_out,
                       j.staff_crossings,
                       j.tickets,
                       j.units,
                       j.revenue,
                       comp.currency_id,
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
                LEFT JOIN analitix_store st ON st.id = j.store_id
                LEFT JOIN res_company comp ON comp.id = st.company_id
            )
        """ % (self._table,))


class AnalitixDoorHourly(models.Model):
    """Per-door traffic. Deliberately carries no conversion: see module docstring."""
    _name = "analitix.door.hourly"
    _description = "Analitix — Hourly Door Traffic"
    _auto = False
    _order = "hour desc"

    store_id = fields.Many2one("analitix.store", string="Store", readonly=True)
    door_id = fields.Many2one("analitix.door", string="Door", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    hour = fields.Datetime(string="Hour", readonly=True)
    visitors_in = fields.Integer(string="Visitors In", readonly=True)
    visitors_out = fields.Integer(string="Visitors Out", readonly=True)
    staff_crossings = fields.Integer(string="Staff Crossings", readonly=True)
    door_share = fields.Float(
        string="Share of Store %", readonly=True, aggregator="avg",
        help="What percentage of the store's entrances that hour came through "
             "this door. Tells the owner which entrance actually carries the "
             "traffic — often not the one they assumed.")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW %s AS (
                WITH per_door AS (
                    SELECT e.store_id, e.door_id,
                           date_trunc('hour', e.event_time) AS hour,
                           SUM(CASE WHEN e.direction = 'in'  AND e.counted
                                    THEN e.count ELSE 0 END) AS visitors_in,
                           SUM(CASE WHEN e.direction = 'out' AND e.counted
                                    THEN e.count ELSE 0 END) AS visitors_out,
                           SUM(CASE WHEN NOT e.counted
                                    THEN e.count ELSE 0 END) AS staff_crossings
                    FROM analitix_event e
                    WHERE e.door_id IS NOT NULL
                    GROUP BY e.store_id, e.door_id,
                             date_trunc('hour', e.event_time)
                )
                -- Stable id, for the reason explained in analitix.hourly above.
                SELECT row_number() OVER (
                           ORDER BY d.store_id, d.door_id, d.hour) AS id,
                       d.store_id,
                       d.door_id,
                       st.company_id,
                       d.hour,
                       d.visitors_in,
                       d.visitors_out,
                       d.staff_crossings,
                       CASE WHEN SUM(d.visitors_in)
                                 OVER (PARTITION BY d.store_id, d.hour) > 0
                            THEN ROUND(100.0 * d.visitors_in / SUM(d.visitors_in)
                                 OVER (PARTITION BY d.store_id, d.hour), 2)
                            ELSE 0.0 END AS door_share
                FROM per_door d
                LEFT JOIN analitix_store st ON st.id = d.store_id
            )
        """ % (self._table,))
