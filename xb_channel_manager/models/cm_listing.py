# -*- coding: utf-8 -*-
import logging
import secrets
from datetime import date, timedelta

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from . import ical_utils

_logger = logging.getLogger(__name__)


class CmListing(models.Model):
    _name = "xb.cm.listing"
    _description = "Channel Room Mapping"
    _order = "channel_id, id"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    channel_id = fields.Many2one(
        "xb.cm.channel", required=True, ondelete="cascade")
    channel_type = fields.Selection(related="channel_id.channel_type")
    company_id = fields.Many2one(related="channel_id.company_id", store=True)
    product_tmpl_id = fields.Many2one(
        "product.template", string="Room type / offer", required=True,
        domain=[("rent_ok", "=", True)],
        help="The rental product that represents this room type.")
    capacity = fields.Integer(
        string="Units (capacity)",
        help="Number of identical units sold on the channel. With the "
             "Hotel industry installed this is taken from the physical "
             "rooms linked to the offer; set it only as an override for "
             "plain Rental databases.")
    effective_capacity = fields.Integer(
        compute="_compute_effective_capacity")

    # --- iCal ---------------------------------------------------------
    export_token = fields.Char(
        readonly=True, copy=False,
        default=lambda self: secrets.token_urlsafe(24))
    ical_export_url = fields.Char(
        compute="_compute_ical_export_url",
        string="Export URL (give to the OTA)")
    ical_import_url = fields.Char(
        string="Import URL (from the OTA)",
        help="The iCal/ics export URL provided by the platform "
             "(e.g. the Airbnb listing calendar export link).")

    # --- Channex ------------------------------------------------------
    channex_room_type_id = fields.Char(string="Channex room type ID")
    channex_rate_plan_id = fields.Char(string="Channex rate plan ID")
    rate_push = fields.Boolean(
        string="Push nightly rate", default=True,
        help="Push the product rental price to the channel (Channex only).")

    reservation_ids = fields.One2many("xb.cm.reservation", "listing_id")
    reservation_count = fields.Integer(compute="_compute_reservation_count")
    last_pull = fields.Datetime(readonly=True)
    last_push = fields.Datetime(readonly=True)

    _uniq_room_per_channel = models.Constraint(
        "unique(channel_id, product_tmpl_id)",
        "This room type is already mapped on this channel.",
    )

    @api.depends("channel_id.name", "product_tmpl_id.name")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s ↔ %s" % (
                rec.channel_id.name or "?",
                rec.product_tmpl_id.name or "?")

    def _compute_reservation_count(self):
        for rec in self:
            rec.reservation_count = len(rec.reservation_ids)

    def _compute_effective_capacity(self):
        engine = self.env["xb.cm.engine"]
        native = engine._has_hotel_industry()
        for rec in self:
            if native and rec.product_tmpl_id.x_resource_ids:
                rec.effective_capacity = len(
                    rec.product_tmpl_id.x_resource_ids)
            else:
                rec.effective_capacity = rec.capacity or 1

    def _compute_ical_export_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url") or ""
        for rec in self:
            rec.ical_export_url = "%s/cm/ical/%s.ics" % (
                base, rec.export_token)

    @api.constrains("capacity")
    def _check_capacity(self):
        for rec in self:
            if rec.capacity < 0:
                raise ValidationError(_("Capacity cannot be negative."))

    def action_regenerate_token(self):
        for rec in self:
            rec.export_token = secrets.token_urlsafe(24)

    def action_pull_now(self):
        self.ensure_one()
        if self.channel_type == "ical":
            self._ical_pull()
        else:
            self._channex_push_ari(self.channel_id._channex_client())
        return True

    def action_view_reservations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reservations"),
            "res_model": "xb.cm.reservation",
            "view_mode": "list,form",
            "domain": [("listing_id", "=", self.id)],
        }

    # ------------------------------------------------------------------
    # iCal EXPORT (used by the HTTP controller)
    # ------------------------------------------------------------------
    def _ical_export_text(self):
        """Generate the .ics feed of fully-booked dates."""
        self.ensure_one()
        engine = self.env["xb.cm.engine"]
        horizon = self.channel_id.export_horizon_days or 365
        date_from = date.today()
        date_to = date_from + timedelta(days=horizon)
        full = engine.get_full_dates(self, date_from, date_to)
        # Merge consecutive dates into ranges (DTEND exclusive)
        events, start, prev = [], None, None
        for d in full:
            if start is None:
                start = prev = d
                continue
            if d == prev + timedelta(days=1):
                prev = d
                continue
            events.append({"start": start, "end": prev + timedelta(days=1)})
            start = prev = d
        if start is not None:
            events.append({"start": start, "end": prev + timedelta(days=1)})
        payload = [{
            "uid": "cm-%s-%s@%s" % (
                self.id, ev["start"].strftime("%Y%m%d"),
                (self.env["ir.config_parameter"].sudo()
                 .get_param("web.base.url") or "odoo")
                .split("//")[-1]),
            "start": ev["start"],
            "end": ev["end"],
            "summary": "Reserved",
        } for ev in events]
        return ical_utils.generate(
            payload, calname=self.product_tmpl_id.name)

    # ------------------------------------------------------------------
    # iCal IMPORT
    # ------------------------------------------------------------------
    def _ical_pull(self):
        """Fetch the OTA feed and upsert staged reservations."""
        self.ensure_one()
        if not self.ical_import_url:
            return
        Log = self.env["xb.cm.log"].sudo()
        try:
            resp = requests.get(self.ical_import_url, timeout=30)
            resp.raise_for_status()
            text = resp.text
        except requests.RequestException as exc:
            Log.log(self.channel_id, "error", "ical_import",
                    "%s: %s" % (self.name, exc), listing=self)
            raise UserError(_(
                "Could not fetch the iCal feed of %(listing)s: %(err)s",
                listing=self.name, err=exc)) from exc
        events = ical_utils.parse(text)
        stats = self.env["xb.cm.reservation"]._upsert_from_ical(
            self, events)
        self.last_pull = fields.Datetime.now()
        Log.log(self.channel_id, "info", "ical_import",
                "%s: %s events — %s new, %s cancelled, %s blocks"
                % (self.name, len(events), stats["new"],
                   stats["cancelled"], stats["blocks"]),
                listing=self)

    # ------------------------------------------------------------------
    # Channex ARI push
    # ------------------------------------------------------------------
    def _channex_push_ari(self, client):
        self.ensure_one()
        if not self.channex_room_type_id:
            return
        engine = self.env["xb.cm.engine"]
        channel = self.channel_id
        horizon = channel.export_horizon_days or 365
        date_from = date.today()
        date_to = date_from + timedelta(days=horizon)
        occ = engine.get_occupancy(self, date_from, date_to)

        # Availability: merge consecutive dates with same free count
        values, run = [], None
        for d in sorted(occ):
            free = max(occ[d][0] - occ[d][1], 0)
            if run and run["availability"] == free and \
                    run["date_to"] == (d - timedelta(days=1)).isoformat():
                run["date_to"] = d.isoformat()
                continue
            run = {
                "property_id": channel.channex_property_id,
                "room_type_id": self.channex_room_type_id,
                "date_from": d.isoformat(),
                "date_to": d.isoformat(),
                "availability": free,
            }
            values.append(run)
        if values:
            client.post("/api/v1/availability", {"values": values})

        # Nightly rate from the rental pricing engine
        if self.rate_push and self.channex_rate_plan_id:
            price = self._nightly_price()
            if price:
                client.post("/api/v1/restrictions", {"values": [{
                    "property_id": channel.channex_property_id,
                    "rate_plan_id": self.channex_rate_plan_id,
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                    "rate": int(round(price * 100)),
                }]})
        self.last_push = fields.Datetime.now()
        self.env["xb.cm.log"].sudo().log(
            self.channel_id, "info", "ari_push",
            "%s: pushed %s availability ranges%s" % (
                self.name, len(values),
                ", rate %.2f" % price
                if self.rate_push and self.channex_rate_plan_id and price
                else ""),
            listing=self)

    def _nightly_price(self):
        """Best nightly price from the rental pricing of the product."""
        self.ensure_one()
        tmpl = self.product_tmpl_id
        pricing = tmpl.product_pricing_ids.filtered(
            lambda p: p.recurrence_id.unit in ("day", "night")
            or "night" in (p.recurrence_id.name or "").lower())
        if not pricing:
            pricing = tmpl.product_pricing_ids
        return pricing[:1].price or tmpl.list_price
