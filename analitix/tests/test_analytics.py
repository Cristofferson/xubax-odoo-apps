# -*- coding: utf-8 -*-
"""The conversion maths.

These are the numbers the owner makes decisions on and the numbers the monthly
subscription is justified by, so each ratio is checked against a hand-computed
value rather than against whatever the view happens to return.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests.common import tagged

from .common import AnalitixCase


@tagged("post_install", "-at_install")
class TestConversionAnalytics(AnalitixCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A fixed hour in the recent past, so nothing lands in two buckets when
        # the suite happens to run at :59.
        cls.slot = fields.Datetime.now().replace(
            minute=0, second=0, microsecond=0) - timedelta(hours=2)

    def _hourly(self, store):
        # flush_all(), not flush_model(): analitix.hourly is a SQL view that
        # reads analitix_event, analitix_store and pos_order directly. Anything
        # still sitting in the ORM cache — the events just created, an area_sqm
        # set two lines ago — is invisible to it until the write reaches
        # PostgreSQL.
        self.env.flush_all()
        return self.env["analitix.hourly"].search([
            ("store_id", "=", store.id), ("hour", "=", self.slot)], limit=1)

    def test_visitors_are_summed_across_all_doors(self):
        for device in self.devices_three[:2]:
            for _ in range(5):
                self.make_event(device, "in", when=self.slot)
        row = self._hourly(self.store_three)
        self.assertEqual(row.visitors_in, 10)

    def test_staff_crossings_stay_out_of_the_visitor_count(self):
        for _ in range(8):
            self.make_event(self.device_one, "in", when=self.slot)
        for _ in range(4):
            self.make_event(self.device_one, "in", when=self.slot, counted=False)

        row = self._hourly(self.store_one)
        self.assertEqual(row.visitors_in, 8)
        self.assertEqual(row.staff_crossings, 4,
                         "excluded traffic must stay visible, not vanish")

    def test_a_non_counting_doors_traffic_is_excluded(self):
        service = self.devices_three[2]
        self.assertFalse(service.door_id.counts_visitors)
        for _ in range(6):
            self.make_event(self.devices_three[0], "in", when=self.slot)
        for _ in range(6):
            self.make_event(service, "in", when=self.slot, counted=False)

        row = self._hourly(self.store_three)
        self.assertEqual(row.visitors_in, 6)

    def test_conversion_and_ticket_metrics(self):
        """20 visitors, 5 tickets, 1000 revenue, 15 units → the whole ratio set."""
        for _ in range(20):
            self.make_event(self.device_one, "in", when=self.slot)
        self._make_pos_orders(self.store_one, count=5, total=200.0, units=3)

        row = self._hourly(self.store_one)
        self.assertEqual(row.visitors_in, 20)
        self.assertEqual(row.tickets, 5)
        self.assertEqual(row.units, 15)
        self.assertAlmostEqual(row.revenue, 1000.0, places=2)
        self.assertAlmostEqual(row.conversion_rate, 25.0, places=2)   # 5/20
        self.assertAlmostEqual(row.atv, 200.0, places=2)              # 1000/5
        self.assertAlmostEqual(row.upt, 3.0, places=2)                # 15/5
        self.assertAlmostEqual(row.revenue_per_visitor, 50.0, places=2)
        self.assertAlmostEqual(row.visitors_per_ticket, 4.0, places=2)

    def test_density_uses_the_stores_area(self):
        self.store_one.area_sqm = 100.0
        for _ in range(50):
            self.make_event(self.device_one, "in", when=self.slot)
        self._make_pos_orders(self.store_one, count=2, total=500.0, units=1)

        row = self._hourly(self.store_one)
        self.assertAlmostEqual(row.revenue_per_sqm, 10.0, places=2)   # 1000/100
        self.assertAlmostEqual(row.visitors_per_sqm, 0.5, places=2)   # 50/100

    def test_an_hour_with_no_visitors_does_not_divide_by_zero(self):
        self._make_pos_orders(self.store_one, count=1, total=100.0, units=1)
        row = self._hourly(self.store_one)
        self.assertEqual(row.visitors_in, 0)
        self.assertEqual(row.conversion_rate, 0.0)

    def test_sales_without_visitors_still_appear(self):
        """A dead counter must look like a problem, not like a quiet morning."""
        self._make_pos_orders(self.store_one, count=3, total=90.0, units=1)
        row = self._hourly(self.store_one)
        self.assertTrue(row, "an hour with sales but no traffic was hidden")
        self.assertEqual(row.tickets, 3)

    def test_door_traffic_reports_each_doors_share(self):
        for _ in range(75):
            self.make_event(self.devices_three[0], "in", when=self.slot)
        for _ in range(25):
            self.make_event(self.devices_three[1], "in", when=self.slot)

        self.env.flush_all()
        rows = self.env["analitix.door.hourly"].search([
            ("store_id", "=", self.store_three.id), ("hour", "=", self.slot)])
        shares = {row.door_id.name: row.door_share for row in rows}
        self.assertAlmostEqual(shares["Street"], 75.0, places=1)
        self.assertAlmostEqual(shares["Gallery"], 25.0, places=1)

    def test_occupancy_never_goes_negative(self):
        """More exits than entrances happens; a negative headcount does not."""
        self.make_event(self.device_one, "in")
        for _ in range(5):
            self.make_event(self.device_one, "out")
        self.store_one.invalidate_recordset()
        self.assertEqual(self.store_one.live_occupancy, 0)

    # ------------------------------------------------------------------
    def _make_pos_orders(self, store, count, total, units):
        """Create paid POS orders attributable to ``store`` at ``self.slot``."""
        product = self.env["product.product"].create({
            "name": "Test Item", "available_in_pos": True, "list_price": total,
            "type": "consu",
        })
        pricelist = self.env["product.pricelist"].create({
            "name": "Test PL", "currency_id": store.company_id.currency_id.id})
        config = self.env["pos.config"].create({
            "name": "Analytics Register %s" % store.code,
            "company_id": store.company_id.id,
        })
        if store.match_mode == "registers":
            store.register_ids = [(4, config.id)]
        config.with_user(self.env.user).open_ui()
        session = self.env["pos.session"].search(
            [("config_id", "=", config.id)], limit=1)
        for index in range(count):
            self.env["pos.order"].create({
                "session_id": session.id,
                "company_id": store.company_id.id,
                "pricelist_id": pricelist.id,
                "date_order": self.slot,
                "amount_tax": 0.0,
                "amount_total": total,
                "amount_paid": total,
                "amount_return": 0.0,
                "state": "paid",
                "lines": [(0, 0, {
                    "product_id": product.id,
                    "qty": units,
                    "price_unit": total / units,
                    "price_subtotal": total,
                    "price_subtotal_incl": total,
                })],
            })
