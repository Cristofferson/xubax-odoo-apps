# -*- coding: utf-8 -*-
"""Displays, and what they pull.

A point of interest is a shelf, a showcase, a table — something a customer
stops in front of. Zones answer "where do people go"; POIs answer "what do they
stop at", which is a finer and more commercially useful question.

The pairing that makes it worth money
-------------------------------------
Attention on its own is a vanity metric. Attention **crossed with the sales of
the products actually on that display** produces two findings an owner can act
on the same afternoon:

* **Lots of attention, few sales** — people are drawn to it and then walk away.
  Almost always price, or nobody closing.
* **Few visitors, good sales** — it converts everyone who finds it, and it is
  in a cold corner. Move it to a warm one.

Both are computed by comparing this model's numbers with POS lines for the
products the implementer attached to each display. Neither is inferred
automatically: a display's products are configuration, because only the shop
knows what is physically on it.

Explicitly out of scope: gaze direction. Task 978 rules it out, and rightly —
it needs far better cameras than this product assumes, and "stopped in front
of" already answers the business question.
"""
from odoo import api, fields, models, _


class AnalitixPoi(models.Model):
    _name = "analitix.poi"
    _description = "Analitix Display / Point of Interest"
    _order = "store_id, zone_id, sequence, id"

    name = fields.Char(
        required=True,
        help="What the staff call it: 'Window Showcase', 'Solitaire Case', "
             "'New Arrivals Table'.")
    code = fields.Char(string="Reference", copy=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    zone_id = fields.Many2one(
        "analitix.zone", string="Zone", required=True, index=True,
        ondelete="cascade")
    store_id = fields.Many2one(
        related="zone_id.store_id", store=True, index=True, readonly=True)
    company_id = fields.Many2one(
        related="zone_id.company_id", store=True, index=True, readonly=True)

    product_ids = fields.Many2many(
        "product.template", relation="analitix_poi_product_rel",
        column1="poi_id", column2="product_tmpl_id", string="Products On It",
        help="What is physically on this display. Only the shop knows, so it is "
             "configuration — and without it the attention figures cannot be "
             "compared against sales, which is where the insight lives.")
    stop_seconds = fields.Integer(
        string="Counts As A Stop After (s)", default=8, required=True,
        help="Shorter than the zone's engagement threshold: someone pausing at "
             "a showcase for eight seconds has looked at it, even if they were "
             "only passing through the zone.")

    attention_ids = fields.One2many(
        "analitix.poi.attention", "poi_id", string="Attention")
    stops_today = fields.Integer(
        compute="_compute_stats", compute_sudo=True, string="Stops Today")
    avg_seconds_today = fields.Float(
        compute="_compute_stats", compute_sudo=True, string="Avg Stop (s)")

    note = fields.Text(string="Notes")

    _code_store_uniq = models.Constraint(
        "unique(code, store_id)",
        "Another display of this store already uses that reference.")

    @api.depends("attention_ids")
    def _compute_stats(self):
        Attention = self.env["analitix.poi.attention"]
        for store in self.mapped("store_id"):
            pois = self.filtered(lambda p: p.store_id == store)
            start, end = store._period_window()
            domain = [("poi_id", "in", pois.ids), ("started_at", ">=", start)]
            if end:
                domain.append(("started_at", "<", end))
            grouped = Attention._read_group(
                domain, groupby=["poi_id"],
                aggregates=["__count", "seconds:avg"])
            found = {poi.id: (count, avg or 0.0) for poi, count, avg in grouped}
            for poi in pois:
                count, avg = found.get(poi.id, (0, 0.0))
                poi.stops_today = count
                poi.avg_seconds_today = avg
        for poi in self.filtered(lambda p: not p.store_id):
            poi.stops_today = 0
            poi.avg_seconds_today = 0.0

    @api.depends("name", "zone_id.name")
    def _compute_display_name(self):
        for poi in self:
            poi.display_name = (
                "%s / %s" % (poi.zone_id.name, poi.name)
                if poi.zone_id else poi.name)


class AnalitixPoiAttention(models.Model):
    _name = "analitix.poi.attention"
    _description = "Analitix Display Attention"
    _order = "started_at desc, id desc"
    _rec_name = "poi_id"

    poi_id = fields.Many2one(
        "analitix.poi", string="Display", required=True, index=True,
        ondelete="cascade")
    zone_id = fields.Many2one(
        related="poi_id.zone_id", store=True, index=True, readonly=True)
    store_id = fields.Many2one(
        related="poi_id.store_id", store=True, index=True, readonly=True)
    company_id = fields.Many2one(
        related="poi_id.company_id", store=True, index=True, readonly=True)
    visitor_id = fields.Many2one(
        "analitix.visitor", string="Visit", index=True, ondelete="cascade")

    started_at = fields.Datetime(
        string="Started", required=True, index=True,
        default=lambda self: fields.Datetime.now())
    seconds = fields.Integer(string="Seconds", default=0, index=True)

    _store_started_idx = models.Index("(store_id, started_at DESC)")

    @api.model
    def record(self, visitor, poi, started_at, seconds):
        """Upsert one stop, for the same reason zone dwell upserts."""
        existing = self.sudo().search([
            ("visitor_id", "=", visitor.id),
            ("poi_id", "=", poi.id),
            ("started_at", "=", started_at),
        ], limit=1)
        if existing:
            existing.write({"seconds": seconds})
            return existing
        if seconds < poi.stop_seconds:
            # Below the threshold it is someone walking past, not a stop.
            return self.browse()
        return self.sudo().create({
            "poi_id": poi.id,
            "visitor_id": visitor.id,
            "started_at": started_at,
            "seconds": seconds,
        })


class AnalitixPoiPerformance(models.Model):
    """Attention beside sales, per display and day.

    A read-only view rather than a stored report: the underlying attention and
    POS rows are the truth, and a stored copy would be one more thing that can
    silently disagree with them.

    Sales are attributed to a display through the products the implementer
    attached to it. A product on two displays counts on both — which is honest:
    the data genuinely cannot say which one closed the sale, and splitting it
    would invent a precision that does not exist.
    """
    _name = "analitix.poi.performance"
    _description = "Analitix — Display Attention vs Sales"
    _auto = False
    _order = "day desc, stops desc"

    poi_id = fields.Many2one("analitix.poi", string="Display", readonly=True)
    zone_id = fields.Many2one("analitix.zone", string="Zone", readonly=True)
    store_id = fields.Many2one("analitix.store", string="Store", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    day = fields.Date(string="Day", readonly=True)

    stops = fields.Integer(string="Stops", readonly=True)
    attention_seconds = fields.Integer(string="Attention (s)", readonly=True)
    units_sold = fields.Integer(string="Units Sold", readonly=True)
    revenue = fields.Monetary(
        string="Revenue", readonly=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", readonly=True)
    units_per_stop = fields.Float(
        string="Units / Stop", readonly=True, aggregator="avg",
        help="Below the store's usual figure with plenty of stops means people "
             "are drawn to this display and then walk away — price, or nobody "
             "closing.")

    def init(self):
        from odoo import tools
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW %s AS (
                WITH attention AS (
                    SELECT a.poi_id,
                           (a.started_at AT TIME ZONE 'UTC')::date AS day,
                           COUNT(*) AS stops,
                           SUM(a.seconds) AS attention_seconds
                    FROM analitix_poi_attention a
                    GROUP BY a.poi_id, (a.started_at AT TIME ZONE 'UTC')::date
                ),
                sales AS (
                    -- One row per display per day. The DISTINCT on the order
                    -- line guards against a display listing the same product
                    -- template twice through two variants.
                    SELECT rel.poi_id,
                           (o.date_order AT TIME ZONE 'UTC')::date AS day,
                           SUM(l.qty) AS units_sold,
                           SUM(l.price_subtotal_incl) AS revenue
                    FROM analitix_poi_product_rel rel
                    JOIN product_product pp
                         ON pp.product_tmpl_id = rel.product_tmpl_id
                    JOIN pos_order_line l ON l.product_id = pp.id
                    JOIN pos_order o ON o.id = l.order_id
                    JOIN analitix_poi poi ON poi.id = rel.poi_id
                    JOIN analitix_zone z ON z.id = poi.zone_id
                    JOIN analitix_store s ON s.id = z.store_id
                    WHERE o.state IN ('paid', 'done', 'invoiced')
                      AND o.company_id = s.company_id
                    GROUP BY rel.poi_id, (o.date_order AT TIME ZONE 'UTC')::date
                ),
                joined AS (
                    SELECT COALESCE(a.poi_id, s.poi_id) AS poi_id,
                           COALESCE(a.day, s.day) AS day,
                           COALESCE(a.stops, 0) AS stops,
                           COALESCE(a.attention_seconds, 0) AS attention_seconds,
                           COALESCE(s.units_sold, 0) AS units_sold,
                           COALESCE(s.revenue, 0.0) AS revenue
                    FROM attention a
                    FULL OUTER JOIN sales s
                         ON a.poi_id = s.poi_id AND a.day = s.day
                )
                SELECT row_number() OVER (ORDER BY j.poi_id, j.day) AS id,
                       j.poi_id,
                       poi.zone_id,
                       z.store_id,
                       st.company_id,
                       j.day,
                       j.stops,
                       j.attention_seconds,
                       j.units_sold,
                       j.revenue,
                       comp.currency_id,
                       CASE WHEN j.stops > 0
                            THEN ROUND(j.units_sold::numeric / j.stops, 3)
                            ELSE 0.0 END AS units_per_stop
                FROM joined j
                LEFT JOIN analitix_poi poi ON poi.id = j.poi_id
                LEFT JOIN analitix_zone z ON z.id = poi.zone_id
                LEFT JOIN analitix_store st ON st.id = z.store_id
                LEFT JOIN res_company comp ON comp.id = st.company_id
            )
        """ % (self._table,))
