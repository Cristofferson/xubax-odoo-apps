# -*- coding: utf-8 -*-
"""1.1: currencies, platform commission, modifications, seasons, minimum
stay and several rate plans per room."""
from datetime import date, timedelta

from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged

from ..models import ical_utils


class FakeClient:
    """Records the Channex calls instead of doing HTTP."""

    def __init__(self, feed=None):
        self.feed = feed or []
        self.posts = []

    def get(self, path, params=None):
        if path.startswith("/api/v1/booking_revisions/feed"):
            return {"data": self.feed}
        return {"data": {}}

    def post(self, path, json=None):
        self.posts.append((path, json))
        return {}


@tagged("standard", "at_install", "-post_install")
class TestChannelV11(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.room = cls.env["product.template"].create({
            "name": "Apartment Centro",
            "type": "service",
            "list_price": 100.0,
        })
        cls.channel = cls.env["xb.cm.channel"].create({
            "name": "Channex PY",
            "channel_type": "channex",
            "state": "connected",
            "auto_import": True,
            "import_policy": "confirm",
            "channex_property_id": "prop-py",
            "modification_policy": "auto",
        })
        cls.listing = cls.env["xb.cm.listing"].create({
            "channel_id": cls.channel.id,
            "product_tmpl_id": cls.room.id,
            "capacity": 1,
            "channex_room_type_id": "rt-1",
            "base_price": 100.0,
        })
        cls.plan_std = cls.env["xb.cm.rate.plan"].create({
            "listing_id": cls.listing.id,
            "name": "Standard",
            "channex_rate_plan_id": "rp-std",
        })
        cls.plan_nr = cls.env["xb.cm.rate.plan"].create({
            "listing_id": cls.listing.id,
            "name": "Non-refundable",
            "channex_rate_plan_id": "rp-nr",
            "percent": -10,
        })
        cls.checkin = date.today() + timedelta(days=40)
        cls.checkout = cls.checkin + timedelta(days=3)
        cls.other = cls.company.currency_id.search([
            ("name", "=", "PYG" if cls.company.currency_id.name != "PYG"
             else "EUR")], limit=1) or cls.env["res.currency"].with_context(
            active_test=False).search([("name", "=", "PYG")], limit=1)

    def _booking(self, uid="BDC-1", status="new", checkin=None,
                 checkout=None, amount="300.00", currency=None,
                 commission=None, rooms=None):
        checkin = checkin or self.checkin
        checkout = checkout or self.checkout
        booking = {
            "status": status,
            "unique_id": uid,
            "ota_name": "Booking.com",
            "currency": currency or self.company.currency_id.name,
            "amount": amount,
            "arrival_date": checkin.isoformat(),
            "departure_date": checkout.isoformat(),
            "customer": {"name": "Ana", "surname": "Benítez",
                         "mail": "ana@example.com", "phone": "+595981"},
            "rooms": rooms or [{
                "room_type_id": "rt-1",
                "rate_plan_id": "rp-std",
                "checkin_date": checkin.isoformat(),
                "checkout_date": checkout.isoformat(),
                "amount": amount,
                "occupancy": {"adults": 2, "children": 0},
            }],
        }
        if commission is not None:
            booking["ota_commission"] = commission
        return booking

    def _upsert(self, booking):
        return self.env["xb.cm.reservation"]._channex_upsert_booking(
            self.channel, booking, booking["unique_id"])

    def _resa(self, uid="BDC-1"):
        return self.env["xb.cm.reservation"].search([
            ("channel_id", "=", self.channel.id),
            ("external_uid", "=", uid)])

    # ------------------------------------------------------------------
    # Currency and commission
    # ------------------------------------------------------------------
    def test_010_foreign_currency_booking(self):
        cur = self.other
        self.assertTrue(cur, "test needs a second currency")
        cur.with_context(active_test=False).active = False
        self._upsert(self._booking(amount="1500000", currency=cur.name,
                                   commission="225000"))
        resa = self._resa()
        self.assertEqual(resa.state, "imported", resa.error_msg)
        self.assertTrue(cur.active, "currency is activated")
        self.assertEqual(resa.currency_id, cur)
        order = resa.sale_order_id
        self.assertEqual(order.currency_id, cur)
        self.assertAlmostEqual(order.amount_total, 1500000)
        self.assertAlmostEqual(resa.commission_amount, 225000)
        self.assertAlmostEqual(resa.net_amount, 1275000)
        self.assertAlmostEqual(order.cm_commission_amount, 225000)
        self.assertAlmostEqual(order.cm_net_amount, 1275000)
        self.assertEqual(order.cm_reservation_id, resa)
        self.assertEqual(resa.rate_plan_id, self.plan_std)

    def test_020_default_commission_percent(self):
        self.channel.commission_percent = 15
        self._upsert(self._booking(amount="300.00"))
        resa = self._resa()
        self.assertAlmostEqual(resa.commission_amount, 45.0)
        self.assertAlmostEqual(resa.sale_order_id.cm_net_amount, 255.0)

    def test_030_multi_room_commission_split(self):
        rooms = []
        for amount in ("200.00", "100.00"):
            rooms.append({
                "room_type_id": "rt-1", "rate_plan_id": "rp-std",
                "checkin_date": self.checkin.isoformat(),
                "checkout_date": self.checkout.isoformat(),
                "amount": amount, "occupancy": {"adults": 1}})
        self.listing.capacity = 2
        self._upsert(self._booking(uid="BDC-M", amount="300.00",
                                   commission="30.00", rooms=rooms))
        r0, r1 = self._resa("BDC-M-0"), self._resa("BDC-M-1")
        self.assertAlmostEqual(r0.commission_amount, 20.0)
        self.assertAlmostEqual(r1.commission_amount, 10.0)
        # the modified booking keeps only the first room
        self._upsert(self._booking(uid="BDC-M", status="modified",
                                   amount="200.00", rooms=rooms[:1]))
        self.assertEqual(r1.state, "cancelled")
        self.assertEqual(r0.state, "imported")

    # ------------------------------------------------------------------
    # Modifications
    # ------------------------------------------------------------------
    def test_040_modification_applied(self):
        self._upsert(self._booking())
        resa = self._resa()
        order = resa.sale_order_id
        new_in = self.checkin + timedelta(days=1)
        new_out = self.checkout + timedelta(days=2)
        self._upsert(self._booking(status="modified", checkin=new_in,
                                   checkout=new_out, amount="420.00"))
        self.assertEqual(resa.state, "imported")
        self.assertFalse(resa.pending_changes)
        self.assertEqual(resa.sale_order_id, order, "same order, updated")
        line = order.order_line.filtered("cm_checkin")
        self.assertEqual(line.cm_checkin, new_in)
        self.assertEqual(line.cm_checkout, new_out)
        self.assertAlmostEqual(order.amount_total, 420.0)
        self.assertIn("changed the reservation",
                      " ".join(order.message_ids.mapped("body")))

    def test_050_modification_conflict(self):
        self._upsert(self._booking(uid="BDC-A"))
        later_in = self.checkout + timedelta(days=5)
        self._upsert(self._booking(uid="BDC-B", checkin=later_in,
                                   checkout=later_in + timedelta(days=2)))
        a = self._resa("BDC-A")
        order = a.sale_order_id
        # A moves onto B's nights → no unit free (capacity 1)
        self._upsert(self._booking(uid="BDC-A", status="modified",
                                   checkin=later_in,
                                   checkout=later_in + timedelta(days=1)))
        self.assertEqual(a.state, "conflict")
        self.assertTrue(a.pending_changes)
        line = order.order_line.filtered("cm_checkin")
        self.assertEqual(line.cm_checkin, self.checkin,
                         "order untouched")

    def test_060_modification_manual_policy(self):
        self.channel.modification_policy = "manual"
        self._upsert(self._booking())
        resa = self._resa()
        new_out = self.checkout + timedelta(days=1)
        self._upsert(self._booking(status="modified", checkout=new_out,
                                   amount="400.00"))
        self.assertTrue(resa.pending_changes)
        line = resa.sale_order_id.order_line.filtered("cm_checkin")
        self.assertEqual(line.cm_checkout, self.checkout)
        resa.action_apply_changes()
        self.assertFalse(resa.pending_changes)
        self.assertEqual(line.cm_checkout, new_out)
        self.assertAlmostEqual(resa.sale_order_id.amount_total, 400.0)

    def test_070_ical_date_change_updates_order(self):
        channel = self.env["xb.cm.channel"].create({
            "name": "Airbnb PY", "channel_type": "ical",
            "state": "connected", "auto_import": True,
            "commission_percent": 10})
        listing = self.env["xb.cm.listing"].create({
            "channel_id": channel.id, "product_tmpl_id": self.room.id,
            "capacity": 3})
        Resa = self.env["xb.cm.reservation"]

        def feed(ci, co):
            return ical_utils.parse(ical_utils.generate([{
                "uid": "air-1", "start": ci, "end": co,
                "summary": "Reserved - Luis"}]))

        Resa._upsert_from_ical(listing, feed(self.checkin, self.checkout))
        resa = Resa.search([("external_uid", "=", "air-1")])
        self.assertEqual(resa.state, "imported")
        new_out = self.checkout + timedelta(days=2)
        Resa._upsert_from_ical(listing, feed(self.checkin, new_out))
        line = resa.sale_order_id.order_line.filtered("cm_checkin")
        self.assertEqual(line.cm_checkout, new_out)
        self.assertEqual(resa.date_to, new_out)
        # no OTA price: gross = order total, commission follows it
        total = resa.sale_order_id.amount_total
        self.assertTrue(total)
        self.assertAlmostEqual(resa.commission_amount, total * 0.10,
                               places=2)
        self.assertAlmostEqual(resa.net_amount, total * 0.90, places=2)

    def test_080_contact_data_not_wiped(self):
        self._upsert(self._booking())
        resa = self._resa()
        booking = self._booking(status="modified")
        booking["customer"] = {"name": "", "surname": ""}
        self._upsert(booking)
        self.assertEqual(resa.guest_email, "ana@example.com")
        self.assertEqual(resa.guest_name, "Ana Benítez")

    # ------------------------------------------------------------------
    # Seasons, minimum stay and rate plans
    # ------------------------------------------------------------------
    def test_090_rate_plans_and_seasons(self):
        start = date.today() + timedelta(days=10)
        self.env["xb.cm.season"].create({
            "channel_id": self.channel.id,
            "name": "High season",
            "date_from": start,
            "date_to": start + timedelta(days=4),
            "price_type": "fixed",
            "price": 150.0,
            "min_stay": 3,
        })
        self.env["xb.cm.season"].create({
            "channel_id": self.channel.id,
            "name": "Holiday",
            "priority": 50,
            "date_from": start + timedelta(days=2),
            "date_to": start + timedelta(days=2),
            "price_type": "percent",
            "percent": 50,
            "stop_sell": True,
        })
        values = self.listing._plan_values(start - timedelta(days=1),
                                           start + timedelta(days=6))
        std = [v for v in values if v["rate_plan_id"] == "rp-std"]
        self.assertEqual(
            [(v["date_from"], v["date_to"], v["rate"],
              v["min_stay_arrival"], v["stop_sell"]) for v in std],
            [((start - timedelta(days=1)).isoformat(),
              (start - timedelta(days=1)).isoformat(), "100.00", 1, False),
             (start.isoformat(), (start + timedelta(days=1)).isoformat(),
              "150.00", 3, False),
             ((start + timedelta(days=2)).isoformat(),
              (start + timedelta(days=2)).isoformat(), "150.00", 1, True),
             ((start + timedelta(days=3)).isoformat(),
              (start + timedelta(days=4)).isoformat(), "150.00", 3, False),
             ((start + timedelta(days=5)).isoformat(),
              (start + timedelta(days=5)).isoformat(), "100.00", 1, False)])
        nr = [v for v in values if v["rate_plan_id"] == "rp-nr"]
        self.assertEqual(nr[1]["rate"], "135.00", "-10 % of 150")
        self.assertTrue(all(v["property_id"] == "prop-py" for v in values))

    def test_100_weekdays_and_plan_min_stay(self):
        start = date.today() + timedelta(days=7)
        start += timedelta(days=(4 - start.weekday()) % 7)  # a Friday
        self.env["xb.cm.season"].create({
            "channel_id": self.channel.id, "name": "Weekend",
            "date_from": start, "date_to": start + timedelta(days=60),
            "price_type": "percent", "percent": 20,
            "mon": False, "tue": False, "wed": False, "thu": False,
            "sun": False,
        })
        self.plan_nr.min_stay = 7
        values = self.listing._plan_values(start, start + timedelta(days=3))
        std = [(v["date_from"], v["rate"]) for v in values
               if v["rate_plan_id"] == "rp-std"]
        # Fri + Sat at +20 % merged in one range, Sunday back to base
        self.assertEqual(std, [
            (start.isoformat(), "120.00"),
            ((start + timedelta(days=2)).isoformat(), "100.00")])
        self.assertTrue(all(v["min_stay_arrival"] == 7 for v in values
                            if v["rate_plan_id"] == "rp-nr"))

    def test_110_channel_currency_conversion(self):
        cur = self.other
        cur.with_context(active_test=False).active = True
        self.env["res.currency.rate"].create({
            "currency_id": cur.id, "company_id": self.company.id,
            "name": date.today() - timedelta(days=1), "rate": 7000.0})
        self.company.currency_id.rate_ids.filtered(
            lambda r: r.company_id == self.company).unlink()
        self.channel.currency_id = cur
        day = date.today() + timedelta(days=3)
        values = self.listing._plan_values(day, day + timedelta(days=1))
        std = [v for v in values if v["rate_plan_id"] == "rp-std"][0]
        expected = self.company.currency_id._convert(
            100.0, cur, self.company, day)
        self.assertEqual(std["rate"], "%.*f" % (cur.decimal_places,
                                                 cur.round(expected)))
        self.channel.min_stay_type = "through"
        values = self.listing._plan_values(day, day + timedelta(days=1))
        self.assertIn("min_stay_through", values[0])

    def test_120_feed_pull_and_ack(self):
        item = {"id": "rev-1", "type": "booking_revision",
                "attributes": dict(self._booking(uid="BDC-F"),
                                   booking_id="bk-F")}
        client = FakeClient(feed=[item])
        self.env["xb.cm.reservation"]._channex_pull_feed(
            self.channel, client)
        resa = self._resa("BDC-F")
        self.assertEqual(resa.state, "imported")
        self.assertEqual(resa.revision_id, "rev-1")
        self.assertIn(("/api/v1/booking_revisions/rev-1/ack", None),
                      client.posts)

    def test_130_push_sends_rates(self):
        client = FakeClient()
        self.listing._channex_push_ari(client)
        paths = [p for p, _j in client.posts]
        self.assertIn("/api/v1/availability", paths)
        self.assertIn("/api/v1/restrictions", paths)
        restr = [j for p, j in client.posts
                 if p == "/api/v1/restrictions"][0]["values"]
        self.assertEqual({v["rate_plan_id"] for v in restr},
                         {"rp-std", "rp-nr"})

    # ------------------------------------------------------------------
    # Multi-company
    # ------------------------------------------------------------------
    def test_140_booking_in_secondary_company(self):
        """A channel of a company that is not the current one (webhook and
        cron run in the main company) still creates its order."""
        company2 = self.env["res.company"].create({"name": "Second Co CM"})
        room2 = self.env["product.template"].create({
            "name": "Apartment Lake", "type": "service",
            "list_price": 80.0, "company_id": company2.id})
        channel2 = self.env["xb.cm.channel"].create({
            "name": "Channex Co2", "channel_type": "channex",
            "company_id": company2.id, "state": "connected",
            "auto_import": True, "import_policy": "confirm",
            "channex_property_id": "prop-2"})
        self.env["xb.cm.listing"].create({
            "channel_id": channel2.id, "product_tmpl_id": room2.id,
            "capacity": 1, "channex_room_type_id": "rt-2"})
        booking = self._booking(uid="CO2-1", amount="240.00",
                                currency=company2.currency_id.name)
        booking["rooms"][0]["room_type_id"] = "rt-2"
        env = self.env(context={"allowed_company_ids": [self.company.id]})
        env["xb.cm.reservation"]._channex_upsert_booking(
            channel2.with_env(env), booking, "CO2-1")
        resa = self.env["xb.cm.reservation"].search([
            ("channel_id", "=", channel2.id), ("external_uid", "=", "CO2-1")])
        self.assertEqual(resa.state, "imported", resa.error_msg)
        self.assertEqual(resa.sale_order_id.company_id, company2)

    def test_150_zero_commission_uses_channel_percent_on_change(self):
        """Channex sends ota_commission "0.00" when the OTA reports none:
        the channel percentage applies, also to the modified total."""
        self.channel.commission_percent = 15.0
        self._upsert(self._booking(uid="ZC-1", amount="200.00",
                                   commission="0.00"))
        resa = self._resa("ZC-1")
        self.assertEqual(resa.state, "imported", resa.error_msg)
        self.assertAlmostEqual(resa.commission_amount, 30.0)
        self._upsert(self._booking(
            uid="ZC-1", status="modified", amount="300.00",
            commission="0.00", checkout=self.checkout + timedelta(days=1)))
        self.assertAlmostEqual(resa.commission_amount, 45.0)
        self.assertAlmostEqual(resa.net_amount, 255.0)

    def test_160_api_key_only_for_admins(self):
        """A channel manager who is not an administrator cannot read the
        Channex key, but the channel still syncs with it."""
        self.channel.channex_api_key = "secret-key"
        user = self.env["res.users"].create({
            "name": "CM manager", "login": "cm.manager.test",
            "group_ids": [Command.set([
                self.env.ref("base.group_user").id,
                self.env.ref("xb_channel_manager.group_cm_manager").id])],
        })
        channel = self.channel.with_user(user)
        self.assertTrue(channel.channex_api_key_set)
        with self.assertRaises(AccessError):
            channel.read(["channex_api_key"])
        self.assertEqual(channel._channex_client().api_key, "secret-key")

    # ------------------------------------------------------------------
    # Plain Sales (Community): stays as order lines with dates
    # ------------------------------------------------------------------
    def _bridge_installed(self):
        return bool(self.env["ir.module.module"].sudo().search([
            ("name", "=", "xb_channel_manager_renting"),
            ("state", "=", "installed")]))

    def test_170_front_desk_order_blocks_the_room(self):
        """A sale made at the front desk (order line with check-in and
        check-out) occupies the room on the channels."""
        order = self.env["sale.order"].create({
            "partner_id": self.env["res.partner"].create({"name": "Walk-in"}).id,
            "order_line": [Command.create({
                "product_id": self.room.product_variant_id.id,
                "cm_checkin": self.checkin,
                "cm_checkout": self.checkout,
            })],
        })
        engine = self.env["xb.cm.engine"]
        self.assertTrue(engine.check_free(
            self.listing, self.checkin, self.checkout), "quotation: free")
        order.action_confirm()
        self.assertFalse(engine.check_free(
            self.listing, self.checkin, self.checkout))
        self.assertEqual(
            engine.get_full_dates(self.listing, self.checkin,
                                  self.checkout + timedelta(days=1)),
            [self.checkin + timedelta(days=i) for i in range(3)])
        # an OTA booking on those nights is a conflict
        self._upsert(self._booking(uid="BDC-CLASH"))
        self.assertEqual(self._resa("BDC-CLASH").state, "conflict")

    def test_180_unpriced_stay_uses_seasons(self):
        """Without an OTA price (iCal), the stay is priced with the
        nightly rates of the room, seasons included."""
        if self._bridge_installed():
            self.skipTest("Rental prices the period with the bridge")
        self.env["xb.cm.season"].create({
            "channel_id": self.channel.id, "name": "High",
            "date_from": self.checkin, "date_to": self.checkin,
            "price_type": "fixed", "price": 150.0})
        channel = self.env["xb.cm.channel"].create({
            "name": "Airbnb Co", "channel_type": "ical",
            "state": "connected", "auto_import": True})
        listing = self.env["xb.cm.listing"].create({
            "channel_id": channel.id, "product_tmpl_id": self.room.id,
            "capacity": 1, "base_price": 100.0})
        self.env["xb.cm.season"].create({
            "channel_id": channel.id, "name": "High",
            "date_from": self.checkin, "date_to": self.checkin,
            "price_type": "fixed", "price": 150.0})
        events = ical_utils.parse(ical_utils.generate([{
            "uid": "air-p", "start": self.checkin, "end": self.checkout,
            "summary": "Reserved"}]))
        self.env["xb.cm.reservation"]._upsert_from_ical(listing, events)
        resa = self.env["xb.cm.reservation"].search([
            ("external_uid", "=", "air-p")])
        self.assertEqual(resa.state, "imported", resa.error_msg)
        line = resa.sale_order_id.order_line
        self.assertEqual(line.cm_checkin, self.checkin)
        # 150 (season) + 100 + 100
        self.assertAlmostEqual(line.price_unit, 350.0)

    def test_190_chatter_note_is_html(self):
        """The import note keeps its line breaks (not escaped <br/>)."""
        self._upsert(self._booking(uid="HTML-1"))
        order = self._resa("HTML-1").sale_order_id
        bodies = " ".join(str(b) for b in order.message_ids.mapped("body"))
        self.assertIn("OTA reservation imported", bodies)
        self.assertNotIn("&lt;br", bodies)

    def test_200_timezone_does_not_depend_on_the_user(self):
        """Check-in hours use the property timezone even when the
        webhook (public user) imports the booking."""
        self.env.company.partner_id.tz = "America/Asuncion"
        engine = self.env["xb.cm.engine"]
        public = self.env.ref("base.public_user")
        public.sudo().tz = "Asia/Tokyo"
        self.assertEqual(
            engine.with_user(public)._property_tz(self.env.company).zone,
            "America/Asuncion")

    def test_210_orders_written_in_property_timezone(self):
        """Orders are created in the property timezone (rental line
        descriptions, reports), whoever runs the import."""
        self.env.company.partner_id.tz = "America/Asuncion"
        self._upsert(self._booking(uid="TZ-1"))
        resa = self._resa("TZ-1")
        engine, rec = self.env["xb.cm.engine"].with_context(
            tz="Asia/Tokyo")._in_company(resa)
        self.assertEqual(engine.env.context.get("tz"), "America/Asuncion")
        self.assertEqual(rec.env.context.get("tz"), "America/Asuncion")
