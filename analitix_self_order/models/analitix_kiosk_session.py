# -*- coding: utf-8 -*-
"""One person (or group) stopping in front of the self-order kiosk.

The kiosk reads its own front camera in the browser and sends one row per stop:
numbers only, never an image. A stop is not a store visit: there is no door
camera behind it, so it lives in its own table instead of inventing visits that
would skew the store's traffic and return-rate reports.
"""
from datetime import timedelta

import pytz

from odoo import api, fields, models
from odoo.addons.analitix.models.analitix_demographic import AGE_BANDS, band_for_age

#: Shorter stops are someone walking past the camera, not a visit to the kiosk.
MIN_SECONDS = 3
#: A quotation or an order made this long after the person left still counts:
#: the kiosk closes the stop when the face is gone, the sale may land a bit later.
OUTCOME_GRACE = timedelta(seconds=120)


class AnalitixKioskSession(models.Model):
    _name = "analitix.kiosk.session"
    _description = "Analitix Kiosk Stop"
    _order = "started_at desc, id desc"
    _rec_name = "started_at"

    uuid = fields.Char(required=True, index=True, readonly=True)
    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade", readonly=True)
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)
    config_id = fields.Many2one(
        "pos.config", string="Kiosk", index=True, ondelete="set null", readonly=True)
    started_at = fields.Datetime(string="Started", required=True, index=True, readonly=True)
    ended_at = fields.Datetime(string="Ended", readonly=True)
    hour = fields.Integer(
        string="Hour", readonly=True, aggregator=False,
        help="Hour of the day in the store's timezone.")
    seconds = fields.Integer(string="Time at the kiosk (s)", readonly=True)
    minutes = fields.Float(
        string="Time at the kiosk (min)", digits=(16, 2), readonly=True, aggregator="avg")
    attention_seconds = fields.Integer(
        string="Facing the screen (s)", readonly=True,
        help="Seconds in which a face was seen looking at the kiosk.")
    people = fields.Integer(
        string="People", readonly=True, default=1, aggregator="avg",
        help="Most faces seen together during the stop.")
    touched = fields.Boolean(string="Used the kiosk", readonly=True, index=True)
    touches = fields.Integer(string="Touches", readonly=True)
    age_band = fields.Selection(AGE_BANDS, string="Age Band", readonly=True, index=True)
    age_confidence = fields.Float(string="Age Confidence", digits=(3, 3), readonly=True,
                                  aggregator="avg")
    gender = fields.Selection(
        [("female", "Female"), ("male", "Male"), ("unknown", "Unknown")],
        string="Gender", default="unknown", readonly=True, index=True)
    gender_confidence = fields.Float(string="Gender Confidence", digits=(3, 3),
                                     readonly=True, aggregator="avg")
    reliable = fields.Boolean(
        string="Reliable", compute="_compute_reliable", store=True,
        help="Age and gender clear the store's confidence floor.")
    outcome = fields.Selection(
        [("none", "Left without buying"),
         ("sale_order", "Quotation or order in Sales"),
         ("pos_order", "Kiosk order")],
        string="Outcome", default="none", readonly=True, index=True)
    converted = fields.Boolean(
        string="Converted", compute="_compute_converted", store=True)
    conversion_rate = fields.Float(
        string="Conversion (%)", compute="_compute_converted", store=True,
        aggregator="avg", digits=(16, 2),
        help="100 when the stop ended in a sale. Its average over a group is the "
             "kiosk's conversion rate.")
    use_rate = fields.Float(
        string="Use (%)", compute="_compute_converted", store=True,
        aggregator="avg", digits=(16, 2),
        help="100 when the person touched the kiosk. Its average is the share of "
             "stops that became a use.")
    sale_order_id = fields.Many2one("sale.order", string="Sales Order", readonly=True,
                                    ondelete="set null")
    pos_order_id = fields.Many2one("pos.order", string="Kiosk Order", readonly=True,
                                   ondelete="set null")
    amount = fields.Monetary(string="Amount", readonly=True, currency_field="currency_id")
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)

    _uuid_unique = models.Constraint("UNIQUE(uuid)", "A kiosk stop is recorded once.")

    @api.depends("age_confidence", "gender_confidence", "store_id.demographic_min_confidence")
    def _compute_reliable(self):
        for stop in self:
            floor = stop.store_id.demographic_min_confidence or 0.0
            scores = [s for s in (stop.age_confidence, stop.gender_confidence) if s]
            stop.reliable = bool(scores) and all(s >= floor for s in scores)

    @api.depends("outcome", "touched")
    def _compute_converted(self):
        for stop in self:
            stop.converted = stop.outcome != "none"
            stop.conversion_rate = 100.0 if stop.converted else 0.0
            stop.use_rate = 100.0 if stop.touched else 0.0

    # ------------------------------------------------------------------
    @api.model
    def _xb_parse_ts(self, value):
        """UTC datetime from the kiosk's epoch milliseconds, or False."""
        try:
            millis = int(value)
        except (TypeError, ValueError):
            return False
        if millis <= 0:
            return False
        return fields.Datetime.to_datetime("1970-01-01") + timedelta(milliseconds=millis)

    @api.model
    def record_from_kiosk(self, config, rows):
        """Store the stops the kiosk sends. Returns the uuids Odoo now holds,
        including the ones it already had, so the kiosk can drop them from its
        queue."""
        store = config.analitix_store_id
        rows = [r for r in rows or [] if isinstance(r, dict) and r.get("uuid")]
        uuids = [str(r["uuid"])[:64] for r in rows]
        held = set(self.search([("uuid", "in", uuids)]).mapped("uuid"))
        tz = pytz.timezone(store.tz or "UTC")
        vals_list = []
        for raw in rows:
            uuid = str(raw["uuid"])[:64]
            if uuid in held:
                continue
            started = self._xb_parse_ts(raw.get("start"))
            ended = self._xb_parse_ts(raw.get("end"))
            if not started or not ended or ended < started:
                held.add(uuid)  # unusable: accepted so the kiosk stops resending it
                continue
            seconds = int((ended - started).total_seconds())
            if seconds < MIN_SECONDS:
                held.add(uuid)
                continue

            def num(key, default=0.0):
                try:
                    return float(raw.get(key) or default)
                except (TypeError, ValueError):
                    return default

            female = raw.get("female")
            gender, gender_conf = "unknown", 0.0
            if female is not None:
                p = min(max(num("female"), 0.0), 1.0)
                gender = "female" if p >= 0.5 else "male"
                gender_conf = round(abs(p - 0.5) * 2, 3)
            age = raw.get("age")
            vals = {
                "uuid": uuid,
                "store_id": store.id,
                "config_id": config.id,
                "started_at": started,
                "ended_at": ended,
                "hour": pytz.utc.localize(started).astimezone(tz).hour,
                "seconds": seconds,
                "minutes": round(seconds / 60.0, 2),
                "attention_seconds": min(int(num("attention")), seconds),
                "people": max(int(num("people", 1)), 1),
                "touched": bool(raw.get("touches")),
                "touches": max(int(num("touches")), 0),
                "age_band": band_for_age(age) if age is not None else False,
                "age_confidence": round(min(max(num("age_confidence"), 0.0), 1.0), 3),
                "gender": gender,
                "gender_confidence": gender_conf,
            }
            vals.update(self._xb_outcome(config, started, ended))
            vals_list.append(vals)
            held.add(uuid)
        if vals_list:
            self.create(vals_list)
        return list(held)

    @api.model
    def _cron_match_outcomes(self):
        """Look again for the sale of recent stops still marked as left without
        buying: an order of the kiosk can land a little after the stop was sent."""
        since = fields.Datetime.now() - OUTCOME_GRACE - timedelta(minutes=10)
        for stop in self.search([("outcome", "=", "none"), ("ended_at", ">=", since),
                                 ("config_id", "!=", False)]):
            vals = self._xb_outcome(stop.config_id, stop.started_at, stop.ended_at)
            if vals["outcome"] != "none":
                stop.write(vals)

    @api.model
    def _xb_outcome(self, config, started, ended):
        """What the stop ended in: an order of this kiosk, or a quotation/order the
        kiosk sent to Sales (its origin is the kiosk's name), made while the
        person was there or right after."""
        window = [started - timedelta(seconds=5), ended + OUTCOME_GRACE]
        taken = self.search([("config_id", "=", config.id),
                             ("started_at", ">=", window[0] - timedelta(hours=1))])
        pos_order = self.env["pos.order"].search([
            ("config_id", "=", config.id),
            ("date_order", ">=", window[0]), ("date_order", "<=", window[1]),
            ("state", "!=", "cancel"),
            ("id", "not in", taken.pos_order_id.ids),
        ], order="date_order", limit=1)
        if pos_order:
            return {"outcome": "pos_order", "pos_order_id": pos_order.id,
                    "amount": pos_order.amount_total}
        sale_order = self.env["sale.order"].search([
            ("origin", "=", config.name),
            ("company_id", "=", config.company_id.id),
            ("create_date", ">=", window[0]), ("create_date", "<=", window[1]),
            ("id", "not in", taken.sale_order_id.ids),
        ], order="create_date", limit=1)
        if sale_order:
            return {"outcome": "sale_order", "sale_order_id": sale_order.id,
                    "amount": sale_order.amount_total}
        return {"outcome": "none"}
