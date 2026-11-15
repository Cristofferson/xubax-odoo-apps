# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.xb_channel_manager.models import ical_utils


@tagged("standard", "at_install")
class TestChannelRenting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.room = cls.env["product.template"].create({
            "name": "Rental Double Room", "type": "service",
            "rent_ok": True, "list_price": 100.0})
        cls.channel = cls.env["xb.cm.channel"].create({
            "name": "Test Airbnb", "channel_type": "ical",
            "state": "connected", "import_policy": "confirm",
            "auto_import": True})
        cls.listing = cls.env["xb.cm.listing"].create({
            "channel_id": cls.channel.id, "product_tmpl_id": cls.room.id,
            "capacity": 1})
        cls.checkin = date.today() + timedelta(days=30)
        cls.checkout = cls.checkin + timedelta(days=3)
        cls.engine = cls.env["xb.cm.engine"]

    def _import(self, uid, ci, co, price=0.0):
        events = ical_utils.parse(ical_utils.generate([{
            "uid": uid, "start": ci, "end": co, "summary": "John Doe"}]))
        Resa = self.env["xb.cm.reservation"]
        self.channel.auto_import = False
        Resa._upsert_from_ical(self.listing, events)
        resa = Resa.search([("external_uid", "=", uid)])
        if price:
            resa.price_total = price
        resa.action_import()
        return resa

    def test_010_ota_booking_is_a_rental_order(self):
        resa = self._import("r-1", self.checkin, self.checkout, 450.0)
        order = resa.sale_order_id
        self.assertTrue(order.is_rental_order)
        line = order.order_line
        self.assertTrue(line.is_rental)
        pickup_h, _return_h = self.engine._checkin_checkout_hours()
        self.assertEqual(line.start_date,
                         self.engine._local_to_utc(self.checkin, pickup_h))
        self.assertEqual(line.return_date.date(), self.checkout)
        self.assertEqual(line.cm_checkin, self.checkin)
        self.assertEqual(line.cm_checkout, self.checkout)
        self.assertAlmostEqual(order.amount_total, 450.0)

    def test_020_front_desk_rental_blocks_the_room(self):
        """A rental order made at the front desk (no Channel Manager
        dates) occupies the room on the channels."""
        pickup_h, return_h = self.engine._checkin_checkout_hours()
        start = self.engine._local_to_utc(self.checkin, pickup_h)
        end = self.engine._local_to_utc(self.checkout, return_h)
        order = self.env["sale.order"].create({
            "partner_id": self.env["res.partner"].create({"name": "Walk-in"}).id,
            "is_rental_order": True,
            "rental_start_date": start, "rental_return_date": end,
            "order_line": [Command.create({
                "product_id": self.room.product_variant_id.id,
                "is_rental": True, "start_date": start,
                "return_date": end})],
        })
        order.action_confirm()
        self.assertFalse(order.order_line.cm_checkin)
        self.assertFalse(self.engine.check_free(
            self.listing, self.checkin, self.checkout))
        clash = self._import("r-clash", self.checkin, self.checkout)
        self.assertEqual(clash.state, "conflict")

    def test_030_date_change_moves_rental_period(self):
        resa = self._import("r-2", self.checkin, self.checkout, 300.0)
        new_out = self.checkout + timedelta(days=2)
        resa._apply_modification({"date_to": new_out})
        line = resa.sale_order_id.order_line
        self.assertEqual(line.return_date.date(), new_out)
        self.assertEqual(line.cm_checkout, new_out)
        self.assertEqual(resa.sale_order_id.rental_return_date.date(),
                         new_out)

    def test_040_post_init_fills_stay_dates(self):
        resa = self._import("r-3", self.checkin, self.checkout, 200.0)
        line = resa.sale_order_id.order_line
        line.write({"cm_checkin": False, "cm_checkout": False})
        from odoo.addons.xb_channel_manager_renting import (
            _post_init_stay_dates)
        _post_init_stay_dates(self.env)
        self.assertEqual(line.cm_checkin, self.checkin)
        self.assertEqual(line.cm_checkout, self.checkout)

