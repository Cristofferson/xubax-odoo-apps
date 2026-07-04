# -*- coding: utf-8 -*-
"""Availability & booking engine shared by all channel drivers.

Two integration levels, detected at runtime:

* **Hotel industry** (Odoo Online "Hotel" industry / booking_engine):
  room offers are ``product.template`` records linked to physical rooms
  (``resource.resource`` via ``x_resource_ids``); nightly occupancy is
  driven by ``planning.slot`` per room and cached in ``x_availability``.
  The engine assigns a free room on import and triggers the native
  recompute, so the website widget and the OTA export stay consistent.

* **Plain Rental** fallback: occupancy is counted from confirmed rental
  order lines of the mapped product; capacity comes from the listing.
"""
import logging
from datetime import date, datetime, time, timedelta

from odoo import _, api, models
from odoo.fields import Command

_logger = logging.getLogger(__name__)


class CmEngine(models.AbstractModel):
    _name = "xb.cm.engine"
    _description = "Channel Manager Engine"

    # ------------------------------------------------------------------
    # Environment capabilities
    # ------------------------------------------------------------------
    @api.model
    def _has_hotel_industry(self):
        return (
            "x_availability" in self.env
            and "planning.slot" in self.env
            and "x_resource_ids" in self.env["product.template"]._fields
        )


    @api.model
    def _slot_sale_link(self):
        """planning.slot ↔ sale.order.line link exists only with
        sale_planning installed."""
        return ("planning.slot" in self.env
                and "sale_line_id" in self.env["planning.slot"]._fields)

    @api.model
    def _checkin_checkout_hours(self):
        """(pickup_hour, return_hour) floats, from the nightly recurrence."""
        try:
            rec = self.env.ref("sale_renting.recurrence_nightly")
            return rec.pickup_time or 15.0, rec.return_time or 12.0
        except ValueError:
            return 15.0, 12.0

    # ------------------------------------------------------------------
    # Occupancy / availability
    # ------------------------------------------------------------------
    @api.model
    def _confirmed_order_nights(self, tmpl, date_from, date_to,
                                exclude_order=None):
        """{date: n_orders} for confirmed rental lines of ``tmpl`` whose
        stay overlaps [date_from, date_to) — checkout day exclusive."""
        domain = [
            ("order_id.state", "=", "sale"),
            ("product_template_id", "=", tmpl.id),
            ("start_date", "<", datetime.combine(date_to, time.max)),
            ("return_date", ">", datetime.combine(date_from, time.min)),
        ]
        if exclude_order:
            domain.append(("order_id", "!=", exclude_order.id))
        counts = {}
        for line in self.env["sale.order.line"].sudo().search(domain):
            if not (line.start_date and line.return_date):
                continue
            start = line.start_date.date()
            end = line.return_date.date()
            nights = max((end - start).days, 1)
            for i in range(nights):
                d = start + timedelta(days=i)
                if date_from <= d < date_to:
                    counts[d] = counts.get(d, 0) + int(line.product_uom_qty
                                                       or 1)
        return counts

    @api.model
    def _slotted_line_ids(self, tmpl):
        """Order line ids of ``tmpl`` already covered by an assigned
        planning slot (their nights already count in x_booked)."""
        if not self._slot_sale_link():
            return set()
        slots = self.env["planning.slot"].sudo().search([
            ("sale_line_id.product_template_id", "=", tmpl.id),
            ("resource_id", "!=", False),
        ])
        return set(slots.mapped("sale_line_id").ids)

    @api.model
    def get_occupancy(self, listing, date_from, date_to):
        """Return {date: (total_units, occupied_units)} for every night
        in [date_from, date_to)."""
        tmpl = listing.product_tmpl_id
        result = {}
        if self._has_hotel_industry() and tmpl.x_resource_ids:
            Avail = self.env["x_availability"].sudo()
            rows = Avail.search([
                ("x_stay_offer_id", "=", tmpl.id),
                ("x_date", ">=", date_from),
                ("x_date", "<", date_to),
            ])
            for row in rows:
                result[row.x_date] = (
                    int(row.x_total_units or 0), int(row.x_booked or 0))
            # Overlay: confirmed orders whose lines have no assigned slot
            # yet (front desk did not assign a room) still occupy a unit.
            slotted = self._slotted_line_ids(tmpl)
            domain_extra = [
                ("order_id.state", "=", "sale"),
                ("product_template_id", "=", tmpl.id),
                ("id", "not in", list(slotted) or [0]),
                ("start_date", "!=", False),
                ("return_date", "!=", False),
            ]
            for line in self.env["sale.order.line"].sudo().search(
                    domain_extra):
                start, end = (line.start_date.date(),
                              line.return_date.date())
                for i in range(max((end - start).days, 1)):
                    d = start + timedelta(days=i)
                    if d in result:
                        total, occ = result[d]
                        result[d] = (total, occ + 1)
            # Nights without an availability row: fall back to capacity
            n_rooms = len(tmpl.x_resource_ids)
            d = date_from
            while d < date_to:
                result.setdefault(d, (n_rooms, 0))
                d += timedelta(days=1)
        else:
            capacity = listing.capacity or 1
            counts = self._confirmed_order_nights(tmpl, date_from, date_to)
            d = date_from
            while d < date_to:
                result[d] = (capacity, counts.get(d, 0))
                d += timedelta(days=1)
        return result

    @api.model
    def get_full_dates(self, listing, date_from, date_to):
        """Sorted list of dates with no free unit (to export as busy)."""
        occ = self.get_occupancy(listing, date_from, date_to)
        return sorted(d for d, (total, used) in occ.items()
                      if total - used <= 0)

    @api.model
    def check_free(self, listing, date_from, date_to, units=1):
        """True if ``units`` are free every night of [date_from, date_to)."""
        occ = self.get_occupancy(listing, date_from, date_to)
        return all(total - used >= units for total, used in occ.values())

    # ------------------------------------------------------------------
    # Booking creation
    # ------------------------------------------------------------------
    @api.model
    def _find_partner(self, name, email=None, phone=None, channel=None):
        Partner = self.env["res.partner"].sudo()
        partner = None
        if email:
            partner = Partner.search([("email", "=ilike", email)], limit=1)
        if not partner and name and phone:
            partner = Partner.search([
                ("name", "=ilike", name), ("phone", "=", phone)], limit=1)
        if not partner:
            partner = Partner.create({
                "name": name or _("OTA Guest"),
                "email": email or False,
                "phone": phone or False,
                "company_type": "person",
                "comment": _("Created by OTA Channel Manager (%s)",
                             channel and channel.name or "iCal"),
            })
        return partner

    @api.model
    def create_booking(self, reservation):
        """Create (and per policy confirm) the sale.order for a staged
        OTA reservation. Returns the sale.order. Raises on conflict."""
        listing = reservation.listing_id
        channel = reservation.channel_id
        tmpl = listing.product_tmpl_id
        checkin, checkout = reservation.date_from, reservation.date_to
        nights = max((checkout - checkin).days, 1)

        if not self.check_free(listing, checkin, checkout):
            raise UserWarningConflict(
                _("No unit free for %(tmpl)s between %(ci)s and %(co)s",
                  tmpl=tmpl.display_name, ci=checkin, co=checkout))

        pickup_h, return_h = self._checkin_checkout_hours()
        start_dt = datetime.combine(
            checkin, time(int(pickup_h), int(pickup_h % 1 * 60)))
        return_dt = datetime.combine(
            checkout, time(int(return_h), int(return_h % 1 * 60)))

        partner = self._find_partner(
            reservation.guest_name, reservation.guest_email,
            reservation.guest_phone, channel)

        variant = tmpl.product_variant_id
        line_vals = {
            "product_id": variant.id,
            "product_uom_qty": 1,
            "is_rental": True,
            "start_date": start_dt,
            "return_date": return_dt,
        }
        # OTA-reported price wins (it is the contractual amount, taxes
        # included); without it the Odoo pricing engine computes it.
        if reservation.price_total:
            line_vals.update({
                "price_unit": reservation.price_total,
                "tax_ids": [Command.clear()],
            })
        order = self.env["sale.order"].sudo().create({
            "partner_id": partner.id,
            "company_id": listing.company_id.id,
            "is_rental_order": True,
            "rental_start_date": start_dt,
            "rental_return_date": return_dt,
            "origin": "%s %s" % (channel.name, reservation.external_uid),
            "client_order_ref": reservation.external_uid[:60],
            "order_line": [Command.create(line_vals)],
        })
        note = _(
            "OTA reservation imported by Channel Manager.<br/>"
            "Channel: %(channel)s<br/>UID: %(uid)s<br/>"
            "Guests: %(guests)s<br/>Raw summary: %(summary)s",
            channel=channel.name, uid=reservation.external_uid,
            guests=reservation.guests or "-",
            summary=reservation.name or "-")
        order.message_post(body=note)

        if channel.import_policy == "confirm":
            order.action_confirm()
            self._assign_room(order, checkin, checkout)
        return order

    # ------------------------------------------------------------------
    # Room assignment + native recompute (Hotel industry only)
    # ------------------------------------------------------------------
    @api.model
    def _free_room(self, tmpl, checkin, checkout):
        """First physical room of the offer with no slot/leave overlap."""
        dt_from = datetime.combine(checkin, time.min)
        dt_to = datetime.combine(checkout, time.max)
        Slot = self.env["planning.slot"].sudo()
        Leave = self.env["resource.calendar.leaves"].sudo()
        for room in tmpl.x_resource_ids:
            busy = Slot.search_count([
                ("resource_id", "=", room.id),
                ("start_datetime", "<", dt_to),
                ("end_datetime", ">", dt_from),
            ])
            if busy:
                continue
            on_leave = Leave.search_count([
                "|", ("resource_id", "=", room.id),
                "&", ("calendar_id", "=", room.calendar_id.id),
                ("resource_id", "=", False),
                ("date_from", "<", dt_to), ("date_to", ">", dt_from),
            ])
            if not on_leave:
                return room
        return self.env["resource.resource"]

    @api.model
    def _assign_room(self, order, checkin, checkout):
        """Assign a free physical room to the order's planning slot so the
        native availability engine (x_booked) blocks the nights."""
        if not self._has_hotel_industry():
            return False
        pickup_h, return_h = self._checkin_checkout_hours()
        start_dt = datetime.combine(
            checkin, time(int(pickup_h), int(pickup_h % 1 * 60)))
        end_dt = datetime.combine(
            checkout, time(int(return_h), int(return_h % 1 * 60)))
        Slot = self.env["planning.slot"].sudo()
        for line in order.order_line.filtered("is_rental"):
            tmpl = line.product_template_id
            if not tmpl.x_resource_ids:
                continue
            room = self._free_room(tmpl, checkin, checkout)
            if not room:
                _logger.warning(
                    "CM: no free room to assign for order %s", order.name)
                continue
            has_link = self._slot_sale_link()
            slot = (Slot.search([("sale_line_id", "=", line.id)], limit=1)
                    if has_link else Slot.browse())
            vals = {
                "resource_id": room.id,
                "start_datetime": start_dt,
                "end_datetime": end_dt,
                "company_id": order.company_id.id,
            }
            if slot:
                slot.write(vals)
            else:
                if "planning_role_id" in tmpl._fields and \
                        tmpl.planning_role_id:
                    vals["role_id"] = tmpl.planning_role_id.id
                if has_link:
                    vals["sale_line_id"] = line.id
                slot = Slot.create(vals)
        self.recompute_availability()
        return True

    @api.model
    def recompute_availability(self):
        """Run the industry's native availability recompute, if present."""
        if "x_availability" not in self.env:
            return
        action = self.env["ir.actions.server"].sudo().search([
            ("name", "ilike", "update_availabilities")], limit=1)
        if not action:
            action = self.env["ir.actions.server"].sudo().search([
                ("model_id.model", "=", "x_availability"),
                ("state", "=", "code"),
                ("code", "ilike", "x_to_recompute"),
            ], limit=1)
        if action:
            try:
                action.run()
            except Exception:  # noqa: BLE001 — never break an import
                _logger.exception("CM: availability recompute failed")

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------
    @api.model
    def cancel_booking(self, reservation):
        order = reservation.sale_order_id
        if not order:
            return
        if self._slot_sale_link():
            self.env["planning.slot"].sudo().search([
                ("sale_line_id", "in", order.order_line.ids)]).unlink()
        if order.state not in ("cancel",):
            order.sudo()._action_cancel()
        order.message_post(body=_(
            "Reservation cancelled on the OTA channel (%s).",
            reservation.channel_id.name))
        self.recompute_availability()


class UserWarningConflict(Exception):
    """Availability conflict while importing an OTA reservation."""
