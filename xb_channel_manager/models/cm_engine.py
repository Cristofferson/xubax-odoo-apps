# -*- coding: utf-8 -*-
"""Availability & booking engine shared by all channel drivers.

Works with plain Sales (Odoo Community): every stay is an order line of
the room product with its own check-in / check-out dates
(``cm_checkin`` / ``cm_checkout``). The free ``xb_channel_manager_renting``
bridge plugs the Rental app in through the ``_stay_*`` hooks below.

Integration levels, detected at runtime:

* **Hotel industry** (Odoo Online "Hotel" industry / booking_engine):
  room offers are ``product.template`` records linked to physical rooms
  (``resource.resource`` via ``x_resource_ids``); nightly occupancy is
  driven by ``planning.slot`` per room and cached in ``x_availability``.
  The engine assigns a free room on import and triggers the native
  recompute, so the website widget and the OTA export stay consistent.

* **Plain Sales / Rental** fallback: occupancy is counted from confirmed
  stay lines of the mapped product; capacity comes from the listing.
"""
import logging
from datetime import date, datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
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

    # ------------------------------------------------------------------
    # Stay lines (hooks overridden by the Rental bridge)
    # ------------------------------------------------------------------
    @api.model
    def _stay_lines(self, order):
        """Order lines that hold a stay."""
        return order.order_line.filtered(
            lambda l: l.cm_checkin and l.cm_checkout)

    @api.model
    def _line_dates(self, line):
        """(check-in date, check-out date) of a stay line."""
        return line.cm_checkin, line.cm_checkout

    @api.model
    def _line_units(self, line):
        """Units (rooms) a stay line occupies every night."""
        return 1

    @api.model
    def _stay_lines_domain(self, tmpl, date_from, date_to):
        """Domain of the stay lines of ``tmpl`` overlapping
        [date_from, date_to) — any order state."""
        return [
            ("product_template_id", "=", tmpl.id),
            ("cm_checkin", "<", date_to),
            ("cm_checkout", ">", date_from),
        ]

    @api.model
    def _stay_line_vals(self, tmpl, checkin, checkout, start_dt, return_dt):
        nights = max((checkout - checkin).days, 1)
        variant = tmpl.product_variant_id
        return {
            "product_id": variant.id,
            "product_uom_qty": 1,
            "name": _("%(room)s\n%(nights)s night(s): %(ci)s → %(co)s",
                      room=variant.display_name, nights=nights,
                      ci=checkin, co=checkout),
            "cm_checkin": checkin,
            "cm_checkout": checkout,
        }

    @api.model
    def _stay_order_vals(self, start_dt, return_dt):
        return {}

    @api.model
    def _stay_computed_price(self, listing, checkin, checkout):
        """Price of a stay the platform did not price (iCal): the nightly
        rates of the room, seasons included. ``None`` lets the Rental
        pricing engine compute it (bridge)."""
        return sum(info["price"] for info in listing._daily_rates(
            checkin, checkout).values())

    @api.model
    def _stay_set_period(self, order, line, checkin, checkout, start_dt,
                         return_dt):
        """Move an existing stay line to new dates."""
        nights = max((checkout - checkin).days, 1)
        line.write({
            "cm_checkin": checkin,
            "cm_checkout": checkout,
            "name": _("%(room)s\n%(nights)s night(s): %(ci)s → %(co)s",
                      room=line.product_id.display_name, nights=nights,
                      ci=checkin, co=checkout),
        })

    @api.model
    def _stay_set_product(self, line, tmpl):
        line.write({"product_id": tmpl.product_variant_id.id})


    @api.model
    def _slot_sale_link(self):
        """planning.slot ↔ sale.order.line link exists only with
        sale_planning installed."""
        return ("planning.slot" in self.env
                and "sale_line_id" in self.env["planning.slot"]._fields)

    @api.model
    def _property_tz(self, company=None):
        """Timezone the check-in/out hours are expressed in: the
        company's website, then the company partner, then the user."""
        company = company or self.env.company
        tz = False
        if "website" in self.env:
            website = self.env["website"].sudo().search(
                [("company_id", "=", company.id)], limit=1)
            tz = website.tz if website and "tz" in website._fields else False
        tz = tz or company.partner_id.tz or self.env.user.tz or "UTC"
        try:
            return pytz.timezone(tz)
        except pytz.UnknownTimeZoneError:
            return pytz.utc

    @api.model
    def _local_to_utc(self, day, hour, company=None):
        """Naive UTC datetime for ``day`` at local float ``hour``."""
        local = datetime.combine(day, time(int(hour), int(hour % 1 * 60)))
        return self._property_tz(company).localize(local).astimezone(
            pytz.utc).replace(tzinfo=None)

    @api.model
    def _checkin_checkout_hours(self):
        """(pickup_hour, return_hour) floats, from the nightly recurrence."""
        try:
            rec = self.env.ref("sale_renting.recurrence_nightly",
                               raise_if_not_found=False)
        except ValueError:
            rec = None
        if rec and "pickup_time" in rec._fields:
            return rec.pickup_time or 15.0, rec.return_time or 12.0
        return 15.0, 12.0

    # ------------------------------------------------------------------
    # Occupancy / availability
    # ------------------------------------------------------------------
    @api.model
    def _confirmed_order_nights(self, tmpl, date_from, date_to,
                                exclude_order=None):
        """{date: units} for confirmed stay lines of ``tmpl`` whose stay
        overlaps [date_from, date_to) — checkout day exclusive."""
        domain = [("order_id.state", "=", "sale")] + self._stay_lines_domain(
            tmpl, date_from, date_to)
        if exclude_order:
            domain.append(("order_id", "!=", exclude_order.id))
        counts = {}
        for line in self.env["sale.order.line"].sudo().search(domain):
            start, end = self._line_dates(line)
            if not (start and end):
                continue
            for i in range(max((end - start).days, 1)):
                d = start + timedelta(days=i)
                if date_from <= d < date_to:
                    counts[d] = counts.get(d, 0) + self._line_units(line)
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
                ("id", "not in", list(slotted) or [0]),
            ] + self._stay_lines_domain(tmpl, date_from, date_to)
            for line in self.env["sale.order.line"].sudo().search(
                    domain_extra):
                start, end = self._line_dates(line)
                if not (start and end):
                    continue
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
    def check_free(self, listing, date_from, date_to, units=1,
                   exclude_order=None):
        """True if ``units`` are free every night of [date_from, date_to).
        ``exclude_order``: nights already held by this (confirmed) order do
        not count — used when the guest changes an existing stay."""
        occ = self.get_occupancy(listing, date_from, date_to)
        if exclude_order and exclude_order.state == "sale":
            for line in self._stay_lines(exclude_order).filtered(
                    lambda l: l.product_template_id
                    == listing.product_tmpl_id):
                start, end = self._line_dates(line)
                if not (start and end):
                    continue
                for i in range(max((end - start).days, 1)):
                    d = start + timedelta(days=i)
                    if d in occ:
                        total, used = occ[d]
                        occ[d] = (total, max(
                            used - self._line_units(line), 0))
        return all(total - used >= units for total, used in occ.values())

    @api.model
    def _pricelist_for(self, currency, company):
        """Pricelist in the reservation currency (the order currency comes
        from its pricelist). Created on the fly for OTA bookings."""
        Pricelist = self.env["product.pricelist"].sudo()
        pricelist = Pricelist.search([
            ("currency_id", "=", currency.id),
            ("company_id", "in", (company.id, False)),
        ], order="company_id desc, sequence, id", limit=1)
        if not pricelist:
            pricelist = Pricelist.create({
                "name": _("OTA bookings (%s)", currency.name),
                "currency_id": currency.id,
                "company_id": company.id,
            })
        return pricelist

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
    def _in_company(self, reservation):
        """Engine and reservation working in the channel company: orders
        of a company other than the main one fail the multi-company
        check otherwise (webhook and cron run in the main company)."""
        company = reservation.channel_id.company_id
        if not company:
            return self, reservation
        return self.with_company(company), reservation.with_company(company)

    @api.model
    def create_booking(self, reservation):
        """Create (and per policy confirm) the sale.order for a staged
        OTA reservation. Returns the sale.order. Raises on conflict."""
        self, reservation = self._in_company(reservation)
        listing = reservation.listing_id
        channel = reservation.channel_id
        tmpl = listing.product_tmpl_id
        checkin, checkout = reservation.date_from, reservation.date_to
        nights = max((checkout - checkin).days, 1)

        if not self.check_free(listing, checkin, checkout):
            raise UserWarningConflict(
                _("No unit free for %(tmpl)s between %(ci)s and %(co)s",
                  tmpl=tmpl.display_name, ci=checkin, co=checkout))

        company = listing.company_id or self.env.company
        pickup_h, return_h = self._checkin_checkout_hours()
        start_dt = self._local_to_utc(checkin, pickup_h, company)
        return_dt = self._local_to_utc(checkout, return_h, company)

        partner = self._find_partner(
            reservation.guest_name, reservation.guest_email,
            reservation.guest_phone, channel)

        variant = tmpl.product_variant_id
        line_vals = self._stay_line_vals(
            tmpl, checkin, checkout, start_dt, return_dt)
        # OTA-reported price wins (it is the contractual amount, taxes
        # included); without it the Odoo pricing engine computes it.
        # The room's own taxes are kept when they are all price-included
        # (the total stays exact and the invoice breaks VAT/lodging tax
        # down); otherwise they are cleared so the total is not inflated.
        if reservation.price_total:
            taxes = variant.taxes_id.filtered(
                lambda t: t.company_id == company)
            keep = taxes and all(t.price_include for t in taxes)
            line_vals.update({
                "price_unit": reservation.price_total,
                "tax_ids": ([Command.set(taxes.ids)] if keep
                            else [Command.clear()]),
            })
        else:
            price = self._stay_computed_price(listing, checkin, checkout)
            if price is not None:
                line_vals["price_unit"] = price
        order_vals = self._stay_order_vals(start_dt, return_dt)
        currency = reservation.currency_id
        if reservation.price_total and currency and \
                currency != company.currency_id:
            order_vals["pricelist_id"] = self._pricelist_for(
                currency, company).id
        order = self.env["sale.order"].sudo().create({
            **order_vals,
            "partner_id": partner.id,
            "company_id": listing.company_id.id,
            "origin": "%s %s" % (channel.name, reservation.external_uid),
            "client_order_ref": reservation.external_uid[:60],
            "cm_reservation_id": reservation.id,
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
        # Hotel industry automations reset rental prices whenever the
        # period or the room slot is written (create, confirm, room
        # assignment): re-apply the OTA amount last.
        if reservation.price_total:
            self._stay_lines(order).write({
                "price_unit": line_vals["price_unit"],
                "tax_ids": line_vals["tax_ids"],
            })
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
        start_dt = self._local_to_utc(checkin, pickup_h, order.company_id)
        end_dt = self._local_to_utc(checkout, return_h, order.company_id)
        Slot = self.env["planning.slot"].sudo()
        for line in self._stay_lines(order):
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
    # Modifications made by the guest on the platform
    # ------------------------------------------------------------------
    @api.model
    def update_booking(self, reservation):
        """Bring the linked order in line with the reservation (dates, room
        type, price, currency). Raises UserWarningConflict when the new
        stay is not available."""
        self, reservation = self._in_company(reservation)
        order = reservation.sale_order_id.sudo()
        if not order or order.state == "cancel":
            return order
        listing = reservation.listing_id
        tmpl = listing.product_tmpl_id
        checkin, checkout = reservation.date_from, reservation.date_to
        line = self._stay_lines(order)[:1]
        if not line:
            return order
        if not self.check_free(listing, checkin, checkout,
                               exclude_order=order):
            raise UserWarningConflict(
                _("No unit free for %(tmpl)s between %(ci)s and %(co)s",
                  tmpl=tmpl.display_name, ci=checkin, co=checkout))
        company = order.company_id
        pickup_h, return_h = self._checkin_checkout_hours()
        start_dt = self._local_to_utc(checkin, pickup_h, company)
        return_dt = self._local_to_utc(checkout, return_h, company)
        old_in, old_out = self._line_dates(line)
        before = "%s → %s, %s" % (
            old_in, old_out, line.product_template_id.display_name)
        if line.product_template_id != tmpl:
            self._stay_set_product(line, tmpl)
        self._stay_set_period(order, line, checkin, checkout, start_dt,
                              return_dt)
        currency = reservation.currency_id
        if reservation.price_total and currency and \
                currency != order.currency_id and order.state == "draft":
            order.pricelist_id = self._pricelist_for(currency, company)
        if order.state == "sale" and self._has_hotel_industry():
            if self._slot_sale_link():
                self.env["planning.slot"].sudo().search([
                    ("sale_line_id", "in", order.order_line.ids)]).unlink()
            self._assign_room(order, checkin, checkout)
        if reservation.price_total:
            taxes = tmpl.product_variant_id.taxes_id.filtered(
                lambda t: t.company_id == company)
            keep = taxes and all(t.price_include for t in taxes)
            line.write({
                "price_unit": reservation.price_total,
                "tax_ids": ([Command.set(taxes.ids)] if keep
                            else [Command.clear()]),
            })
        else:
            price = self._stay_computed_price(listing, checkin, checkout)
            if price is not None:
                line.price_unit = price
        self._sync_order_money(reservation)
        order.message_post(body=_(
            "The guest changed the reservation on %(channel)s.<br/>"
            "Before: %(before)s<br/>Now: %(ci)s → %(co)s, %(room)s, "
            "total %(total)s %(cur)s",
            channel=reservation.channel_id.name, before=before,
            ci=checkin, co=checkout, room=tmpl.display_name,
            total=reservation.price_total or order.amount_total,
            cur=order.currency_id.name))
        return order

    @api.model
    def _sync_order_money(self, reservation):
        """Copy the platform commission to the order (order currency)."""
        self, reservation = self._in_company(reservation)
        order = reservation.sale_order_id.sudo()
        if not order:
            return
        commission = reservation.commission_amount or 0.0
        cur = reservation.currency_id
        if commission and cur and cur != order.currency_id:
            commission = cur._convert(
                commission, order.currency_id, order.company_id,
                reservation.date_from or fields.Date.today())
        order.cm_commission_amount = commission

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------
    @api.model
    def cancel_booking(self, reservation):
        self, reservation = self._in_company(reservation)
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
