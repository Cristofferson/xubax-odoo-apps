# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo.tests.common import TransactionCase, tagged

from ..models import ical_utils


def _ics(uid, start, end, summary="Guest Name"):
    return ical_utils.generate([{
        "uid": uid, "start": start, "end": end, "summary": summary}])


@tagged("standard", "at_install")
class TestChannelFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.room = cls.env["product.template"].create({
            "name": "Test Double Room",
            "type": "service",
            "rent_ok": True,
            "list_price": 100.0,
        })
        cls.channel = cls.env["xb.cm.channel"].create({
            "name": "Test Airbnb",
            "channel_type": "ical",
            "ota_name": "airbnb",
            "state": "connected",
            "import_policy": "confirm",
            "auto_import": False,
        })
        cls.listing = cls.env["xb.cm.listing"].create({
            "channel_id": cls.channel.id,
            "product_tmpl_id": cls.room.id,
            "capacity": 2,
        })
        cls.checkin = date.today() + timedelta(days=30)
        cls.checkout = cls.checkin + timedelta(days=3)

    def _stage(self, uid="resa-1", summary="John Doe", price=0.0):
        events = ical_utils.parse(_ics(uid, self.checkin, self.checkout,
                                       summary))
        self.env["xb.cm.reservation"]._upsert_from_ical(
            self.listing, events)
        resa = self.env["xb.cm.reservation"].search([
            ("external_uid", "=", uid)])
        if price:
            resa.price_total = price
        return resa

    # ------------------------------------------------------------------
    def test_010_staging_upsert(self):
        resa = self._stage()
        self.assertEqual(resa.state, "new")
        self.assertEqual(resa.kind, "reservation")
        self.assertEqual(resa.date_from, self.checkin)
        self.assertEqual(resa.date_to, self.checkout)
        self.assertEqual(resa.nights, 3)
        # idempotent: same feed again does not duplicate
        self._stage()
        self.assertEqual(self.env["xb.cm.reservation"].search_count([
            ("external_uid", "=", "resa-1")]), 1)

    def test_020_import_creates_confirmed_order(self):
        resa = self._stage(price=450.0)
        resa.action_import()
        self.assertEqual(resa.state, "imported")
        order = resa.sale_order_id
        self.assertTrue(order)
        self.assertEqual(order.state, "sale")
        self.assertTrue(order.is_rental_order)
        line = order.order_line
        self.assertEqual(len(line), 1)
        self.assertEqual(line.product_template_id, self.room)
        self.assertEqual(line.start_date.date(), self.checkin)
        self.assertEqual(line.return_date.date(), self.checkout)
        # OTA price honoured exactly (taxes cleared)
        self.assertAlmostEqual(order.amount_total, 450.0)
        self.assertEqual(order.partner_id.name, "John Doe")

    def test_030_draft_policy(self):
        self.channel.import_policy = "draft"
        resa = self._stage(uid="resa-draft")
        resa.action_import()
        self.assertEqual(resa.sale_order_id.state, "draft")

    def test_040_overbooking_guard(self):
        # capacity 2 → two imports fine, third conflicts
        for i in range(2):
            self._stage(uid="resa-cap-%s" % i).action_import()
        third = self._stage(uid="resa-cap-2")
        third.action_import()
        self.assertEqual(third.state, "conflict")
        self.assertFalse(third.sale_order_id)
        self.assertIn("No unit free", third.error_msg or "")

    def test_050_availability_export_full_dates(self):
        for i in range(2):
            self._stage(uid="resa-full-%s" % i).action_import()
        engine = self.env["xb.cm.engine"]
        full = engine.get_full_dates(
            self.listing, self.checkin - timedelta(days=2),
            self.checkout + timedelta(days=2))
        self.assertEqual(full, [self.checkin + timedelta(days=i)
                                for i in range(3)])
        # and the generated feed contains exactly that busy range
        text = self.listing._ical_export_text()
        events = ical_utils.parse(text)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["start"], self.checkin)
        self.assertEqual(events[0]["end"], self.checkout)

    def test_060_cancellation_auto(self):
        self.channel.cancel_policy = "auto"
        resa = self._stage(uid="resa-cxl")
        resa.action_import()
        order = resa.sale_order_id
        # feed now comes back EMPTY → reservation disappeared on the OTA
        self.env["xb.cm.reservation"]._upsert_from_ical(self.listing, [])
        self.assertEqual(resa.state, "cancelled")
        self.assertEqual(order.state, "cancel")

    def test_070_blocks_are_not_imported(self):
        events = ical_utils.parse(_ics(
            "blk-1", self.checkin, self.checkout,
            summary="Airbnb (Not available)"))
        self.env["xb.cm.reservation"]._upsert_from_ical(
            self.listing, events)
        blk = self.env["xb.cm.reservation"].search([
            ("external_uid", "=", "blk-1")])
        self.assertEqual(blk.kind, "block")
        self.assertEqual(blk.state, "ignored")
        blk.action_import()  # no-op for blocks
        self.assertFalse(blk.sale_order_id)

    def test_080_channex_booking_mapping(self):
        """Map a Channex-style webhook payload without any HTTP."""
        channel = self.env["xb.cm.channel"].create({
            "name": "Test Channex",
            "channel_type": "channex",
            "state": "connected",
            "auto_import": True,
            "import_policy": "confirm",
            "channex_property_id": "prop-1",
        })
        self.env["xb.cm.listing"].create({
            "channel_id": channel.id,
            "product_tmpl_id": self.room.id,
            "capacity": 2,
            "channex_room_type_id": "rt-99",
        })
        booking = {
            "status": "new",
            "unique_id": "BDC-123456789",
            "ota_name": "Booking.com",
            "arrival_date": self.checkin.isoformat(),
            "departure_date": self.checkout.isoformat(),
            "amount": "390.00",
            "customer": {"name": "Maria", "surname": "Lopez",
                         "mail": "maria@example.com", "phone": "555123"},
            "rooms": [{
                "room_type_id": "rt-99",
                "checkin_date": self.checkin.isoformat(),
                "checkout_date": self.checkout.isoformat(),
                "amount": "390.00",
                "occupancy": {"adults": 2, "children": 1},
            }],
        }
        self.env["xb.cm.reservation"]._channex_upsert_booking(
            channel, booking, "bk-1")
        resa = self.env["xb.cm.reservation"].search([
            ("external_uid", "=", "BDC-123456789")])
        self.assertEqual(resa.state, "imported")
        self.assertEqual(resa.guest_name, "Maria Lopez")
        self.assertAlmostEqual(resa.sale_order_id.amount_total, 390.0)
        # cancellation webhook
        booking["status"] = "cancelled"
        channel.cancel_policy = "auto"
        self.env["xb.cm.reservation"]._channex_upsert_booking(
            channel, booking, "bk-1")
        self.assertEqual(resa.state, "cancelled")
        self.assertEqual(resa.sale_order_id.state, "cancel")

    def test_090_export_controller_token(self):
        """The ics text is served only for the right token."""
        self.assertTrue(self.listing.export_token)
        text = self.listing._ical_export_text()
        self.assertIn("BEGIN:VCALENDAR", text)
