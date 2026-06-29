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

    company_id = fields.Many2one("res.company", string="Store / Company", readonly=True)
    pos_config_id = fields.Many2one("pos.config", string="POS Register / Store", readonly=True)
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
        # Two scopes, unioned:
        #  * register-scoped: a device tied to a specific pos.config — conversion
        #    is crossed against THAT register's orders only (needed when several
        #    stores share one company, e.g. LAMUR Américas/Centro/Camelinas).
        #  * company-scoped: a device with no pos.config — crossed against the
        #    whole company (single-store company, e.g. Anello).
        # A register that has its own counter device is excluded from the
        # company scope so its sales are never double-counted.
        self.env.cr.execute("""
            CREATE VIEW %s AS (
                WITH cfg_devices AS (
                    SELECT DISTINCT pos_config_id
                    FROM xb_footfall_device
                    WHERE pos_config_id IS NOT NULL
                ),
                co_devices AS (
                    SELECT DISTINCT company_id
                    FROM xb_footfall_device
                    WHERE pos_config_id IS NULL
                ),
                cfg_visits AS (
                    SELECT d.pos_config_id AS pos_config_id,
                           date_trunc('hour', e.event_time) AS hour,
                           SUM(CASE WHEN e.direction = 'in'  THEN e.count ELSE 0 END) AS visitors_in,
                           SUM(CASE WHEN e.direction = 'out' THEN e.count ELSE 0 END) AS visitors_out
                    FROM xb_footfall_event e
                    JOIN xb_footfall_device d ON d.id = e.device_id
                    WHERE d.pos_config_id IS NOT NULL
                    GROUP BY d.pos_config_id, date_trunc('hour', e.event_time)
                ),
                cfg_sales AS (
                    SELECT o.config_id AS pos_config_id,
                           date_trunc('hour', o.date_order) AS hour,
                           COUNT(*) AS tickets,
                           SUM(o.amount_total) AS revenue
                    FROM pos_order o
                    WHERE o.state IN ('paid', 'done', 'invoiced')
                      AND o.config_id IN (SELECT pos_config_id FROM cfg_devices)
                    GROUP BY o.config_id, date_trunc('hour', o.date_order)
                ),
                co_visits AS (
                    SELECT d.company_id AS company_id,
                           date_trunc('hour', e.event_time) AS hour,
                           SUM(CASE WHEN e.direction = 'in'  THEN e.count ELSE 0 END) AS visitors_in,
                           SUM(CASE WHEN e.direction = 'out' THEN e.count ELSE 0 END) AS visitors_out
                    FROM xb_footfall_event e
                    JOIN xb_footfall_device d ON d.id = e.device_id
                    WHERE d.pos_config_id IS NULL
                    GROUP BY d.company_id, date_trunc('hour', e.event_time)
                ),
                co_sales AS (
                    SELECT o.company_id AS company_id,
                           date_trunc('hour', o.date_order) AS hour,
                           COUNT(*) AS tickets,
                           SUM(o.amount_total) AS revenue
                    FROM pos_order o
                    WHERE o.state IN ('paid', 'done', 'invoiced')
                      AND o.company_id IN (SELECT company_id FROM co_devices)
                      AND o.config_id NOT IN (SELECT pos_config_id FROM cfg_devices)
                    GROUP BY o.company_id, date_trunc('hour', o.date_order)
                ),
                unified AS (
                    SELECT COALESCE(v.pos_config_id, s.pos_config_id) AS pos_config_id,
                           NULL::integer AS company_id,
                           COALESCE(v.hour, s.hour) AS hour,
                           COALESCE(v.visitors_in, 0) AS visitors_in,
                           COALESCE(v.visitors_out, 0) AS visitors_out,
                           COALESCE(s.tickets, 0) AS tickets,
                           COALESCE(s.revenue, 0.0) AS revenue
                    FROM cfg_visits v
                    FULL OUTER JOIN cfg_sales s
                         ON v.pos_config_id = s.pos_config_id AND v.hour = s.hour
                    UNION ALL
                    SELECT NULL::integer AS pos_config_id,
                           COALESCE(v.company_id, s.company_id) AS company_id,
                           COALESCE(v.hour, s.hour) AS hour,
                           COALESCE(v.visitors_in, 0) AS visitors_in,
                           COALESCE(v.visitors_out, 0) AS visitors_out,
                           COALESCE(s.tickets, 0) AS tickets,
                           COALESCE(s.revenue, 0.0) AS revenue
                    FROM co_visits v
                    FULL OUTER JOIN co_sales s
                         ON v.company_id = s.company_id AND v.hour = s.hour
                )
                SELECT row_number() OVER () AS id,
                       u.pos_config_id,
                       COALESCE(u.company_id, pc.company_id) AS company_id,
                       u.hour,
                       u.visitors_in,
                       u.visitors_out,
                       u.tickets,
                       u.revenue,
                       comp.currency_id AS currency_id,
                       CASE WHEN u.visitors_in > 0
                            THEN ROUND(100.0 * u.tickets / u.visitors_in, 2)
                            ELSE 0.0 END AS conversion_rate
                FROM unified u
                LEFT JOIN pos_config pc ON pc.id = u.pos_config_id
                LEFT JOIN res_company comp
                     ON comp.id = COALESCE(u.company_id, pc.company_id)
            )
        """ % (self._table,))
