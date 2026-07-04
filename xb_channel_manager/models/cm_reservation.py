# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

from .cm_engine import UserWarningConflict
from . import ical_utils

_logger = logging.getLogger(__name__)


class CmReservation(models.Model):
    _name = "xb.cm.reservation"
    _description = "OTA Reservation (staging inbox)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_from desc, id desc"
    _rec_name = "display_label"

    display_label = fields.Char(compute="_compute_display_label")
    channel_id = fields.Many2one(
        "xb.cm.channel", required=True, ondelete="cascade", index=True)
    listing_id = fields.Many2one(
        "xb.cm.listing", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="channel_id.company_id", store=True)
    product_tmpl_id = fields.Many2one(
        related="listing_id.product_tmpl_id", store=True)

    external_uid = fields.Char(
        string="External UID", required=True, index=True)
    kind = fields.Selection([
        ("reservation", "Reservation"),
        ("block", "Availability block"),
    ], default="reservation", required=True)
    name = fields.Char(string="Summary")
    guest_name = fields.Char()
    guest_email = fields.Char()
    guest_phone = fields.Char()
    guests = fields.Char(string="Guests (adults/children)")
    date_from = fields.Date(string="Check-in", required=True)
    date_to = fields.Date(string="Check-out", required=True)
    nights = fields.Integer(compute="_compute_nights", store=True)
    price_total = fields.Float(
        help="Total amount reported by the OTA (taxes included). "
             "0 = let Odoo compute the price.")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id)
    raw_payload = fields.Text(readonly=True)

    state = fields.Selection([
        ("new", "New"),
        ("imported", "Imported"),
        ("conflict", "Conflict"),
        ("cancelled", "Cancelled"),
        ("ignored", "Ignored"),
        ("error", "Error"),
    ], default="new", required=True, tracking=True, index=True)
    error_msg = fields.Text(readonly=True)
    sale_order_id = fields.Many2one("sale.order", readonly=True, copy=False)

    _uniq_uid_per_channel = models.Constraint(
        "unique(channel_id, external_uid)",
        "This external reservation is already staged for this channel.",
    )

    @api.depends("guest_name", "name", "external_uid")
    def _compute_display_label(self):
        for rec in self:
            rec.display_label = (rec.guest_name or rec.name
                                 or rec.external_uid or "?")

    @api.depends("date_from", "date_to")
    def _compute_nights(self):
        for rec in self:
            rec.nights = ((rec.date_to - rec.date_from).days
                          if rec.date_from and rec.date_to else 0)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_import(self):
        engine = self.env["xb.cm.engine"]
        for rec in self:
            if rec.state in ("imported",) or rec.kind == "block":
                continue
            try:
                order = engine.create_booking(rec)
                rec.write({"state": "imported", "sale_order_id": order.id,
                           "error_msg": False})
            except UserWarningConflict as exc:
                rec.write({"state": "conflict", "error_msg": str(exc)})
                rec._notify_manager(_(
                    "Availability conflict importing an OTA reservation"))
            except Exception as exc:  # noqa: BLE001
                _logger.exception("CM import failed for %s",
                                  rec.external_uid)
                rec.write({"state": "error", "error_msg": str(exc)})
        return True

    def action_ignore(self):
        self.write({"state": "ignored"})

    def action_reset(self):
        self.write({"state": "new", "error_msg": False})

    def action_open_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": self.sale_order_id.id,
            "view_mode": "form",
        }

    def _notify_manager(self, summary):
        for rec in self:
            rec.activity_schedule(
                "mail.mail_activity_data_warning",
                summary=summary,
                note=rec.error_msg or "",
                user_id=(rec.channel_id.create_uid.id
                         or self.env.ref("base.user_admin").id))

    def _mark_cancelled(self):
        """Feed/webhook says the reservation is gone."""
        engine = self.env["xb.cm.engine"]
        for rec in self:
            if rec.state == "cancelled":
                continue
            if rec.sale_order_id and \
                    rec.channel_id.cancel_policy == "auto":
                engine.cancel_booking(rec)
            elif rec.sale_order_id:
                rec._notify_manager(_(
                    "OTA reservation cancelled on the channel — review "
                    "the linked order %s", rec.sale_order_id.name))
            rec.state = "cancelled"

    # ------------------------------------------------------------------
    # iCal upsert
    # ------------------------------------------------------------------
    @api.model
    def _upsert_from_ical(self, listing, events):
        """Sync staged rows with the parsed feed of one listing."""
        channel = listing.channel_id
        stats = {"new": 0, "cancelled": 0, "blocks": 0}
        seen_uids = set()
        for ev in events:
            uid = ev["uid"]
            seen_uids.add(uid)
            existing = self.search([
                ("channel_id", "=", channel.id),
                ("external_uid", "=", uid)], limit=1)
            is_block = ical_utils.is_block(ev)
            guest = (ev.get("summary") or "").strip()
            # Airbnb-style summaries: "Reserved", "Reserved - John Doe"
            for prefix in ("reserved -", "reserved–", "reserved"):
                if guest.lower().startswith(prefix):
                    guest = guest[len(prefix):].strip(" -–")
                    break
            vals = {
                "channel_id": channel.id,
                "listing_id": listing.id,
                "external_uid": uid,
                "kind": "block" if is_block else "reservation",
                "name": ev.get("summary") or "",
                "guest_name": None if is_block else (guest or None),
                "date_from": ev["start"],
                "date_to": ev["end"],
                "raw_payload": ev.get("description") or "",
            }
            if existing:
                # Dates changed on the OTA → update if not imported yet;
                # imported orders get flagged for manual review.
                if (existing.date_from != ev["start"]
                        or existing.date_to != ev["end"]):
                    if existing.state == "imported":
                        existing._notify_manager(_(
                            "Dates changed on the OTA for an imported "
                            "reservation — review order %s",
                            existing.sale_order_id.name))
                    else:
                        existing.write({"date_from": ev["start"],
                                        "date_to": ev["end"]})
                continue
            rec = self.create(vals)
            if is_block:
                stats["blocks"] += 1
                rec.state = "ignored"  # visible but not importable
            else:
                stats["new"] += 1
                if channel.auto_import:
                    rec.action_import()
        # Cancellations: previously staged (this listing) missing now
        missing = self.search([
            ("listing_id", "=", listing.id),
            ("external_uid", "not in", list(seen_uids) or ["-"]),
            ("state", "in", ("new", "imported", "conflict", "error")),
            ("date_to", ">=", fields.Date.today()),
        ])
        if missing:
            missing._mark_cancelled()
            stats["cancelled"] = len(missing)
        return stats

    # ------------------------------------------------------------------
    # Channex bookings feed
    # ------------------------------------------------------------------
    @api.model
    def _channex_pull_feed(self, channel, client):
        """Consume the Channex bookings feed (with acknowledge)."""
        feed = client.get(
            "/api/v1/bookings_feed",
            params={"filter[property_id]": channel.channex_property_id})
        for item in feed.get("data", []):
            try:
                self._channex_stage_event(channel, client, item)
                client.post("/api/v1/bookings_feed/%s/ack" % item.get("id"))
            except Exception as exc:  # noqa: BLE001
                _logger.exception("CM channex feed item failed")
                self.env["xb.cm.log"].sudo().log(
                    channel, "error", "webhook",
                    "feed item %s: %s" % (item.get("id"), exc))

    @api.model
    def _channex_stage_event(self, channel, client, item):
        attrs = item.get("attributes", item) or {}
        booking_id = (attrs.get("booking_id")
                      or item.get("booking_id") or item.get("id"))
        booking = attrs
        if client and booking_id and "rooms" not in attrs:
            data = client.get("/api/v1/bookings/%s" % booking_id)
            booking = (data.get("data") or {}).get("attributes", {})
        return self._channex_upsert_booking(channel, booking, booking_id)

    @api.model
    def _channex_upsert_booking(self, channel, booking, booking_id):
        """Map one Channex booking payload into the staging inbox."""
        status = (booking.get("status") or "new").lower()
        uid = str(booking.get("unique_id")
                  or booking.get("ota_reservation_code")
                  or booking_id)
        customer = booking.get("customer") or {}
        guest_name = " ".join(filter(None, [
            customer.get("name"), customer.get("surname")])) or None
        rooms = booking.get("rooms") or []
        created = self.env["xb.cm.reservation"]
        for i, room in enumerate(rooms):
            room_type = str(room.get("room_type_id") or "")
            listing = channel.listing_ids.filtered(
                lambda l, rt=room_type: l.channex_room_type_id == rt)[:1]
            if not listing:
                self.env["xb.cm.log"].sudo().log(
                    channel, "warning", "webhook",
                    "Booking %s: no listing mapped for room type %s"
                    % (uid, room_type))
                continue
            ext_uid = uid if len(rooms) == 1 else "%s-%s" % (uid, i)
            existing = self.search([
                ("channel_id", "=", channel.id),
                ("external_uid", "=", ext_uid)], limit=1)
            if status in ("cancelled", "canceled"):
                if existing:
                    existing._mark_cancelled()
                continue
            if existing:
                continue
            amount = float(room.get("amount")
                           or booking.get("amount") or 0)
            occupancy = room.get("occupancy") or {}
            rec = self.create({
                "channel_id": channel.id,
                "listing_id": listing.id,
                "external_uid": ext_uid,
                "kind": "reservation",
                "name": "%s (%s)" % (
                    booking.get("ota_name") or "Channex", status),
                "guest_name": guest_name,
                "guest_email": customer.get("mail")
                or customer.get("email"),
                "guest_phone": customer.get("phone"),
                "guests": "%s adults, %s children" % (
                    occupancy.get("adults", "?"),
                    occupancy.get("children", 0)),
                "date_from": room.get("checkin_date")
                or booking.get("arrival_date"),
                "date_to": room.get("checkout_date")
                or booking.get("departure_date"),
                "price_total": amount,
                "raw_payload": str(booking)[:5000],
            })
            created |= rec
            if channel.auto_import:
                rec.action_import()
        return created
