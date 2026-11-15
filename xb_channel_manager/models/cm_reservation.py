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
    date_from = fields.Date(string="Check-in", required=True, tracking=True)
    date_to = fields.Date(string="Check-out", required=True, tracking=True)
    nights = fields.Integer(compute="_compute_nights", store=True)
    price_total = fields.Monetary(
        string="Total (gross)", currency_field="currency_id", tracking=True,
        help="Total amount reported by the OTA (taxes included). "
             "0 = let Odoo compute the price.")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id,
        help="Currency the guest paid in on the platform.")
    commission_amount = fields.Monetary(
        string="Platform commission", currency_field="currency_id",
        tracking=True)
    net_amount = fields.Monetary(
        string="Net income", currency_field="currency_id",
        compute="_compute_net_amount", store=True)
    rate_plan_id = fields.Many2one(
        "xb.cm.rate.plan", string="Rate plan", ondelete="set null")
    revision_id = fields.Char(
        string="Last revision", readonly=True,
        help="Identifier of the last version received from the channel.")
    pending_changes = fields.Boolean(
        readonly=True,
        help="The platform changed this reservation and the changes are "
             "not applied to the order yet.")
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

    @api.depends("price_total", "commission_amount",
                 "sale_order_id.amount_total")
    def _compute_net_amount(self):
        for rec in self:
            # iCal reservations carry no price: the order total is the gross
            gross = rec.price_total or (rec.sale_order_id.amount_total
                                        if rec.sale_order_id else 0.0)
            rec.net_amount = gross - (rec.commission_amount or 0)

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
                           "error_msg": False, "pending_changes": False})
                rec._default_commission()
                engine._sync_order_money(rec)
            except UserWarningConflict as exc:
                rec.write({"state": "conflict", "error_msg": str(exc)})
                rec._notify_manager(_(
                    "Availability conflict importing an OTA reservation"))
            except Exception as exc:  # noqa: BLE001
                _logger.exception("CM import failed for %s",
                                  rec.external_uid)
                rec.write({"state": "error", "error_msg": str(exc)})
        return True

    def _default_commission(self):
        """Commission from the channel percentage when the OTA did not
        report one."""
        for rec in self:
            pct = rec.channel_id.commission_percent
            if rec.commission_amount or not pct:
                continue
            total = rec.price_total
            if not total and rec.sale_order_id:
                total = rec.sale_order_id.amount_total
                if not rec.price_total:
                    rec.currency_id = rec.sale_order_id.currency_id
            if total:
                rec.commission_amount = rec.currency_id.round(
                    total * pct / 100.0)

    def action_apply_changes(self):
        """Apply the changes received from the platform to the order."""
        engine = self.env["xb.cm.engine"]
        for rec in self:
            if not rec.sale_order_id:
                continue
            try:
                engine.update_booking(rec)
                rec.write({"state": "imported", "pending_changes": False,
                           "error_msg": False})
                if not rec.price_total and rec.channel_id.commission_percent:
                    # priced by Odoo: the commission follows the new total
                    rec.commission_amount = 0.0
                    rec._default_commission()
                    engine._sync_order_money(rec)
            except UserWarningConflict as exc:
                rec.write({"state": "conflict", "error_msg": str(exc)})
                rec._notify_manager(_(
                    "The guest changed the reservation on the platform but "
                    "the new dates are not available"))
        return True

    def _apply_modification(self, vals):
        """The platform changed this reservation: store the new values and
        update the order according to the channel policy."""
        self.ensure_one()
        tracked = ("date_from", "date_to", "listing_id", "price_total",
                   "currency_id", "commission_amount", "rate_plan_id",
                   "guests")
        changed = {}
        for key, value in vals.items():
            current = self[key]
            if key in ("listing_id", "currency_id", "rate_plan_id"):
                current = current.id
            elif key in ("date_from", "date_to") and value:
                value = fields.Date.to_date(value)
            if key in ("guest_name", "guest_email", "guest_phone") \
                    and not value:
                continue  # contact data is wiped by some OTAs afterwards
            if current != value:
                changed[key] = value
        if not changed:
            return False
        self.write(changed)
        if not any(k in tracked for k in changed):
            return False
        if self.state in ("conflict", "error") and not self.sale_order_id:
            self.state = "new"
            if self.channel_id.auto_import:
                self.action_import()
            return True
        if not self.sale_order_id or self.state == "cancelled":
            return True
        if self.channel_id.modification_policy == "auto":
            self.pending_changes = True
            self.action_apply_changes()
        else:
            self.pending_changes = True
            self._notify_manager(_(
                "The guest changed the reservation on the platform — review "
                "and apply the changes to order %s",
                self.sale_order_id.name))
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
                if existing.kind == "reservation" and \
                        existing.state not in ("cancelled", "ignored"):
                    existing._apply_modification({
                        "date_from": ev["start"], "date_to": ev["end"]})
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
    # Channex booking revisions feed
    # ------------------------------------------------------------------
    @api.model
    def _channex_pull_feed(self, channel, client):
        """Consume the Channex booking revisions feed (oldest first) and
        acknowledge every revision once it is staged."""
        feed = client.get("/api/v1/booking_revisions/feed", params={
            "filter[property_id]": channel.channex_property_id,
            "order[inserted_at]": "asc",
        })
        for item in feed.get("data", []):
            try:
                with self.env.cr.savepoint():
                    self._channex_stage_event(channel, client, item)
                client.post("/api/v1/booking_revisions/%s/ack"
                            % item.get("id"))
            except Exception as exc:  # noqa: BLE001
                _logger.exception("CM channex feed item failed")
                self.env["xb.cm.log"].sudo().log(
                    channel, "error", "webhook",
                    "revision %s: %s" % (item.get("id"), exc))

    @api.model
    def _channex_stage_event(self, channel, client, item):
        attrs = item.get("attributes", item) or {}
        booking_id = (attrs.get("booking_id")
                      or item.get("booking_id") or item.get("id"))
        booking = dict(attrs)
        if client and booking_id and "rooms" not in attrs:
            data = client.get("/api/v1/bookings/%s" % booking_id)
            booking = (data.get("data") or {}).get("attributes", {})
        booking.setdefault("revision_id", item.get("id")
                           if item.get("type") == "booking_revision"
                           else attrs.get("revision_id"))
        return self._channex_upsert_booking(channel, booking, booking_id)

    @api.model
    def _channex_currency(self, code, channel):
        """res.currency for an ISO code; inactive currencies are activated
        (the guest really paid in it)."""
        if not code:
            return channel.company_id.currency_id
        currency = self.env["res.currency"].sudo().with_context(
            active_test=False).search([("name", "=", code.upper())], limit=1)
        if not currency:
            raise ValueError(_("Unknown currency %s", code))
        if not currency.active:
            currency.active = True
            self.env["xb.cm.log"].sudo().log(
                channel, "info", "webhook",
                "Currency %s activated for OTA bookings" % currency.name)
        return currency

    @staticmethod
    def _amount(value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @api.model
    def _channex_upsert_booking(self, channel, booking, booking_id):
        """Map one Channex booking (revision) into the staging inbox:
        new rooms are created, changed ones are modified, removed or
        cancelled ones are cancelled."""
        status = (booking.get("status") or "new").lower()
        uid = str(booking.get("unique_id")
                  or booking.get("ota_reservation_code")
                  or booking_id)
        customer = booking.get("customer") or {}
        guest_name = " ".join(filter(None, [
            customer.get("name"), customer.get("surname")])) or None
        rooms = booking.get("rooms") or []
        currency = self._channex_currency(booking.get("currency"), channel)
        booking_amount = self._amount(booking.get("amount"))
        commission = booking.get("ota_commission")
        commission = (self._amount(commission)
                      if commission not in (None, "") else None)
        room_amounts = [self._amount(r.get("amount")) for r in rooms]
        rooms_total = sum(room_amounts) or booking_amount
        existing_all = self.search([
            ("channel_id", "=", channel.id),
            "|", ("external_uid", "=", uid),
            ("external_uid", "=like", uid + "-%")])

        if status in ("cancelled", "canceled"):
            existing_all._mark_cancelled()
            for rec in existing_all:
                rec.revision_id = booking.get("revision_id") or rec.revision_id
            return existing_all

        result = self.browse()
        seen = self.browse()
        for i, room in enumerate(rooms):
            room_type = str(room.get("room_type_id") or "")
            listing = channel.listing_ids.filtered(
                lambda l, rt=room_type: l.channex_room_type_id == rt)[:1]
            if not listing:
                self.env["xb.cm.log"].sudo().log(
                    channel, "warning", "webhook",
                    "Booking %s: no room mapped for Channex room type %s"
                    % (uid, room_type))
                continue
            # Keep the identifiers stable when a modification adds or
            # removes rooms: «uid» for a single room, «uid-N» otherwise.
            has_plain = bool(existing_all.filtered(
                lambda r: r.external_uid == uid))
            has_suffix = bool(existing_all - existing_all.filtered(
                lambda r: r.external_uid == uid))
            if i == 0 and (has_plain or (len(rooms) == 1
                                         and not has_suffix)):
                ext_uid = uid
            else:
                ext_uid = "%s-%s" % (uid, i)
            amount = room_amounts[i] or (
                booking_amount if len(rooms) == 1 else 0.0)
            room_commission = None
            if commission is not None:
                share = (amount / rooms_total) if rooms_total else (
                    1.0 / len(rooms))
                room_commission = currency.round(commission * share)
            plan_ext = str(room.get("rate_plan_id") or "")
            plan = listing.rate_plan_ids.filtered(
                lambda p, pe=plan_ext: p.channex_rate_plan_id == pe)[:1]
            occupancy = room.get("occupancy") or booking.get(
                "occupancy") or {}
            vals = {
                "listing_id": listing.id,
                "guests": "%s adults, %s children" % (
                    occupancy.get("adults", "?"),
                    occupancy.get("children", 0)),
                "date_from": room.get("checkin_date")
                or booking.get("arrival_date"),
                "date_to": room.get("checkout_date")
                or booking.get("departure_date"),
                "price_total": amount,
                "currency_id": currency.id,
                "rate_plan_id": plan.id or False,
                "guest_name": guest_name,
                "guest_email": customer.get("mail") or customer.get("email"),
                "guest_phone": customer.get("phone"),
            }
            if room_commission is not None:
                vals["commission_amount"] = room_commission
            existing = existing_all.filtered(
                lambda r, e=ext_uid: r.external_uid == e)[:1]
            if existing:
                seen |= existing
                existing.write({
                    "revision_id": booking.get("revision_id")
                    or existing.revision_id,
                    "raw_payload": str(booking)[:5000],
                })
                if existing.state != "cancelled":
                    existing._apply_modification(vals)
                result |= existing
                continue
            vals.update({
                "channel_id": channel.id,
                "external_uid": ext_uid,
                "kind": "reservation",
                "name": "%s (%s)" % (
                    booking.get("ota_name") or "Channex", status),
                "revision_id": booking.get("revision_id"),
                "raw_payload": str(booking)[:5000],
            })
            rec = self.create(vals)
            result |= rec
            if channel.auto_import:
                rec.action_import()
        # rooms removed from a modified booking
        gone = (existing_all - seen).filtered(
            lambda r: r.state != "cancelled")
        if gone and rooms:
            gone._mark_cancelled()
        return result
