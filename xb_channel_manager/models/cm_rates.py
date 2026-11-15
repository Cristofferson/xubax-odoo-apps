# -*- coding: utf-8 -*-
"""Rates sent to the channels: seasons (price and minimum stay per date)
and several rate plans per room (standard, non-refundable, weekly…)."""
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class CmSeason(models.Model):
    _name = "xb.cm.season"
    _description = "Channel Season / Date Rule"
    _order = "priority desc, date_from, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    channel_id = fields.Many2one(
        "xb.cm.channel", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="channel_id.company_id", store=True)
    currency_id = fields.Many2one(related="channel_id.company_currency_id")
    date_from = fields.Date(required=True)
    date_to = fields.Date(
        required=True, help="Last night of the season (inclusive).")
    priority = fields.Integer(
        default=10,
        help="When several rules apply to the same night, the highest "
             "priority wins (e.g. a holiday inside the high season).")
    listing_ids = fields.Many2many(
        "xb.cm.listing", string="Rooms",
        domain="[('channel_id', '=', channel_id)]",
        help="Leave empty to apply to every room of the channel.")
    price_type = fields.Selection([
        ("none", "Keep the base price"),
        ("fixed", "Fixed nightly price"),
        ("percent", "Percentage over the base price"),
    ], default="percent", required=True)
    price = fields.Monetary(
        string="Nightly price", currency_field="currency_id")
    percent = fields.Float(
        string="Adjustment (%)",
        help="+20 = 20 % more expensive, -15 = 15 % cheaper.")
    min_stay = fields.Integer(
        string="Minimum stay (nights)",
        help="0 = no minimum. Sent to the channel for every night of the "
             "season.")
    closed_to_arrival = fields.Boolean(
        help="Guests cannot check in on these nights.")
    stop_sell = fields.Boolean(
        string="Stop sell", help="Close the sale on the channel.")
    mon = fields.Boolean(default=True)
    tue = fields.Boolean(default=True)
    wed = fields.Boolean(default=True)
    thu = fields.Boolean(default=True)
    fri = fields.Boolean(default=True)
    sat = fields.Boolean(default=True)
    sun = fields.Boolean(default=True)

    @api.constrains("date_from", "date_to", "min_stay")
    def _check_dates(self):
        for rec in self:
            if rec.date_to < rec.date_from:
                raise ValidationError(_(
                    "The season «%s» ends before it starts.", rec.name))
            if rec.min_stay < 0:
                raise ValidationError(_(
                    "The minimum stay cannot be negative."))

    def _applies(self, listing, day):
        self.ensure_one()
        return (self.date_from <= day <= self.date_to
                and getattr(self, WEEKDAYS[day.weekday()])
                and (not self.listing_ids or listing in self.listing_ids))


class CmRatePlan(models.Model):
    _name = "xb.cm.rate.plan"
    _description = "Channel Rate Plan"
    _order = "listing_id, sequence, id"

    name = fields.Char(required=True, default=lambda self: _("Standard"))
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    listing_id = fields.Many2one(
        "xb.cm.listing", required=True, ondelete="cascade", index=True)
    channel_id = fields.Many2one(
        related="listing_id.channel_id", store=True)
    currency_id = fields.Many2one(
        related="listing_id.channel_id.company_currency_id")
    channex_rate_plan_id = fields.Char(
        string="Channex rate plan ID", required=True)
    percent = fields.Float(
        string="Adjustment (%)",
        help="Applied over the price of each night: -10 for a "
             "non-refundable rate 10 % cheaper.")
    amount = fields.Monetary(
        string="Adjustment (amount)", currency_field="currency_id",
        help="Fixed amount added to each night (negative to discount).")
    min_stay = fields.Integer(
        string="Minimum stay (nights)",
        help="Minimum stay of this rate (e.g. 7 for a weekly rate). The "
             "highest of the season and the rate is sent.")

    _sql_constraints = [
        ("uniq_rate_plan", "unique(listing_id, channex_rate_plan_id)",
         "This Channex rate plan is already mapped on this room."),
    ]

    def _apply(self, price, min_stay):
        self.ensure_one()
        price = price * (1 + (self.percent or 0) / 100.0) + (self.amount or 0)
        return max(price, 0.0), max(min_stay or 0, self.min_stay or 0)


class CmListingRates(models.Model):
    _inherit = "xb.cm.listing"

    base_price = fields.Monetary(
        string="Base nightly price", currency_field="company_currency_id",
        help="Price per night sent to the channels before seasons and rate "
             "plans. Leave 0 to use the price of the product.")
    company_currency_id = fields.Many2one(
        related="channel_id.company_currency_id")
    rate_plan_ids = fields.One2many("xb.cm.rate.plan", "listing_id")

    def _base_price(self):
        self.ensure_one()
        return self.base_price or self._nightly_price()

    def _daily_rates(self, date_from, date_to):
        """{date: {price, min_stay, closed_to_arrival, stop_sell}} for every
        night in [date_from, date_to), in the company currency, before the
        rate plan adjustments."""
        self.ensure_one()
        base = self._base_price()
        seasons = self.env["xb.cm.season"].search([
            ("channel_id", "=", self.channel_id.id),
            ("date_from", "<", date_to),
            ("date_to", ">=", date_from),
        ])
        result = {}
        day = date_from
        while day < date_to:
            price, min_stay, cta, stop = base, 0, False, False
            season = seasons.filtered(
                lambda s, d=day: s._applies(self, d))[:1]
            if season:
                if season.price_type == "fixed":
                    price = season.price
                elif season.price_type == "percent":
                    price = base * (1 + (season.percent or 0) / 100.0)
                min_stay = season.min_stay
                cta = season.closed_to_arrival
                stop = season.stop_sell
            result[day] = {"price": price, "min_stay": min_stay,
                           "closed_to_arrival": cta, "stop_sell": stop}
            day += timedelta(days=1)
        return result

    def _plan_values(self, date_from, date_to):
        """Channex restriction values for every rate plan of the room,
        merged into ranges of consecutive identical nights (date_to
        inclusive). Prices are converted to the channel currency."""
        self.ensure_one()
        channel = self.channel_id
        plans = self.rate_plan_ids.filtered("active")
        daily = self._daily_rates(date_from, date_to)
        company = channel.company_id
        src = company.currency_id
        dst = channel.currency_id or src
        values = []
        for plan in plans:
            run = None
            for day in sorted(daily):
                info = daily[day]
                price, min_stay = plan._apply(info["price"], info["min_stay"])
                if dst != src:
                    price = src._convert(price, dst, company, day)
                key = (dst.round(price), min_stay or 1,
                       bool(info["closed_to_arrival"]),
                       bool(info["stop_sell"]))
                if run and run["_key"] == key and \
                        run["date_to"] == (day - timedelta(days=1)).isoformat():
                    run["date_to"] = day.isoformat()
                    continue
                run = {
                    "_key": key,
                    "property_id": channel.channex_property_id,
                    "rate_plan_id": plan.channex_rate_plan_id,
                    "date_from": day.isoformat(),
                    "date_to": day.isoformat(),
                }
                values.append(run)
        min_stay_field = ("min_stay_through"
                          if channel.min_stay_type == "through"
                          else "min_stay_arrival")
        out = []
        for val in values:
            price, min_stay, cta, stop = val.pop("_key")
            val.update({
                # decimal string: works for currencies without cents (PYG)
                "rate": "%.*f" % (dst.decimal_places, price),
                min_stay_field: min_stay,
                "closed_to_arrival": cta,
                "stop_sell": stop,
            })
            if price <= 0:
                del val["rate"]
            out.append(val)
        return out

    def action_open_rates_preview(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Rates sent to the channel"),
            "res_model": "xb.cm.rate.preview",
            "view_mode": "form",
            "target": "new",
            "context": {"default_listing_id": self.id},
        }


class CmRatePreview(models.TransientModel):
    _name = "xb.cm.rate.preview"
    _description = "Preview of the rates sent to the channel"

    listing_id = fields.Many2one("xb.cm.listing", required=True)
    date_from = fields.Date(required=True, default=fields.Date.today)
    days = fields.Integer(default=60)
    line_ids = fields.One2many("xb.cm.rate.preview.line", "preview_id")

    def action_compute(self):
        self.ensure_one()
        self.line_ids.unlink()
        date_to = self.date_from + timedelta(days=max(self.days, 1))
        lines = []
        for val in self.listing_id._plan_values(self.date_from, date_to):
            plan = self.listing_id.rate_plan_ids.filtered(
                lambda p, v=val: p.channex_rate_plan_id == v["rate_plan_id"])
            lines.append({
                "preview_id": self.id,
                "rate_plan_id": plan[:1].id,
                "date_from": val["date_from"],
                "date_to": val["date_to"],
                "rate": float(val.get("rate") or 0),
                "min_stay": val.get("min_stay_arrival")
                or val.get("min_stay_through") or 1,
                "closed_to_arrival": val["closed_to_arrival"],
                "stop_sell": val["stop_sell"],
            })
        self.env["xb.cm.rate.preview.line"].create(lines)
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class CmRatePreviewLine(models.TransientModel):
    _name = "xb.cm.rate.preview.line"
    _description = "Preview line"
    _order = "rate_plan_id, date_from"

    preview_id = fields.Many2one("xb.cm.rate.preview", ondelete="cascade")
    rate_plan_id = fields.Many2one("xb.cm.rate.plan")
    date_from = fields.Date()
    date_to = fields.Date()
    rate = fields.Float(string="Nightly price (channel currency)")
    min_stay = fields.Integer()
    closed_to_arrival = fields.Boolean()
    stop_sell = fields.Boolean()
