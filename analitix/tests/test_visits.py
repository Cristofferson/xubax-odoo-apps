# -*- coding: utf-8 -*-
"""Phase 2: visits, re-identification, demographics and purchase units.

The theme running through this file is that phase 2 exists to stop the system
lying to the owner in two specific ways:

* counting one person's four crossings as four visitors, and
* counting a family of four as four failed sales.

Both are checked here against numbers worked out by hand, and both are checked
on a one-door store *and* a three-door store, because the whole product promise
is that neither shape is special.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests.common import tagged

from .common import AnalitixCase


@tagged("post_install", "-at_install")
class TestVisitResolution(AnalitixCase):

    def setUp(self):
        super().setUp()
        self.crypto = self.env["analitix.crypto"]
        self.Signature = self.env["analitix.face.signature"]
        self.Visitor = self.env["analitix.visitor"]
        self.Group = self.env["analitix.visit.group"]

    def _crossing(self, device, vector, direction="in", when=None):
        """A crossing carrying an encrypted face, as the ingest endpoint parks it."""
        return self.make_event(
            device, direction, when=when,
            pending_embedding=self.crypto.encrypt_vector(
                self.crypto.normalize(vector)))

    def _resolve(self, events):
        job = self.env["analitix.job"].enqueue(
            "visitor_resolve", {"event_ids": events.ids},
            store=events[0].store_id)
        job._run_one()
        events.invalidate_recordset()
        return job

    # ------------------------------------------------------------------
    # The core promise
    # ------------------------------------------------------------------
    def test_the_same_face_resolves_to_one_signature(self):
        face = self.fake_vector(101)
        first = self._crossing(self.device_one, face)
        self._resolve(first)
        second = self._crossing(self.device_one, face)
        self._resolve(second)

        self.assertTrue(first.signature_id)
        self.assertEqual(first.signature_id, second.signature_id,
                         "the same person became two people")

    def test_two_different_faces_stay_two_people(self):
        one = self._crossing(self.device_one, self.fake_vector(1))
        self._resolve(one)
        two = self._crossing(self.device_one, self.fake_vector(999))
        self._resolve(two)
        self.assertNotEqual(one.signature_id, two.signature_id)

    def test_stepping_out_and_back_is_one_visit(self):
        """The headline reason this phase exists."""
        face = self.fake_vector(7)
        start = fields.Datetime.now() - timedelta(minutes=20)

        entry = self._crossing(self.device_one, face, "in", when=start)
        self._resolve(entry)
        leave = self._crossing(self.device_one, face, "out",
                               when=start + timedelta(minutes=5))
        self._resolve(leave)
        back = self._crossing(self.device_one, face, "in",
                              when=start + timedelta(minutes=8))
        self._resolve(back)

        visits = self.Visitor.search([("store_id", "=", self.store_one.id)])
        self.assertEqual(len(visits), 1, "one person became %d visits" % len(visits))
        self.assertEqual(visits.state, "inside")
        self.assertEqual(visits.re_entry_count, 1)

    def test_coming_back_after_the_gap_is_a_new_visit(self):
        self.store_one.visit_gap_minutes = 10
        face = self.fake_vector(11)
        start = fields.Datetime.now() - timedelta(hours=3)

        self._resolve(self._crossing(self.device_one, face, "in", when=start))
        self._resolve(self._crossing(
            self.device_one, face, "out", when=start + timedelta(minutes=5)))
        self._resolve(self._crossing(
            self.device_one, face, "in", when=start + timedelta(minutes=90)))

        visits = self.Visitor.search([("store_id", "=", self.store_one.id)])
        self.assertEqual(len(visits), 2, "a genuine second trip was merged away")

    def test_the_gap_is_per_store(self):
        """A boutique and a corner shop cannot share one threshold."""
        self.store_one.visit_gap_minutes = 60
        self.store_three.visit_gap_minutes = 2
        self.assertNotEqual(self.store_one.visit_gap_minutes,
                            self.store_three.visit_gap_minutes)

        face = self.fake_vector(13)
        start = fields.Datetime.now() - timedelta(hours=2)
        for device, store in ((self.device_one, self.store_one),
                              (self.devices_three[0], self.store_three)):
            self._resolve(self._crossing(device, face, "in", when=start))
            self._resolve(self._crossing(
                device, face, "out", when=start + timedelta(minutes=1)))
            self._resolve(self._crossing(
                device, face, "in", when=start + timedelta(minutes=30)))

        self.assertEqual(len(self.Visitor.search(
            [("store_id", "=", self.store_one.id)])), 1)
        self.assertEqual(len(self.Visitor.search(
            [("store_id", "=", self.store_three.id)])), 2)

    # ------------------------------------------------------------------
    # Doors
    # ------------------------------------------------------------------
    def test_entering_and_leaving_by_different_doors_is_one_visit(self):
        """The reason a multi-door store buys re-identification at all."""
        face = self.fake_vector(21)
        start = fields.Datetime.now() - timedelta(minutes=15)

        entry = self._crossing(self.devices_three[0], face, "in", when=start)
        self._resolve(entry)
        exit_ = self._crossing(self.devices_three[1], face, "out",
                               when=start + timedelta(minutes=10))
        self._resolve(exit_)

        visits = self.Visitor.search([("store_id", "=", self.store_three.id)])
        self.assertEqual(len(visits), 1)
        self.assertEqual(visits.door_id, self.doors_three[0])
        self.assertEqual(visits.exit_door_id, self.doors_three[1])
        self.assertEqual(visits.state, "left")

    def test_a_signature_remembers_which_doors_were_used(self):
        face = self.fake_vector(23)
        self._resolve(self._crossing(self.devices_three[0], face, "in"))
        self._resolve(self._crossing(self.devices_three[1], face, "out"))
        signature = self.Signature.search(
            [("store_id", "=", self.store_three.id)], limit=1)
        self.assertEqual(len(signature.door_ids), 2)

    def test_faces_never_match_across_stores(self):
        """Two customers on one instance must not be joined by a face."""
        face = self.fake_vector(31)
        self._resolve(self._crossing(self.device_one, face))
        self._resolve(self._crossing(self.devices_three[0], face))

        self.assertEqual(len(self.Signature.search(
            [("store_id", "=", self.store_one.id)])), 1)
        self.assertEqual(len(self.Signature.search(
            [("store_id", "=", self.store_three.id)])), 1,
            "a face from store A leaked into store B")

    # ------------------------------------------------------------------
    # Staff and liveness
    # ------------------------------------------------------------------
    def test_an_employee_never_becomes_a_visit(self):
        employee = self.env["hr.employee"].create({"name": "Hugo"})
        face = self.fake_vector(41)
        self.env["analitix.staff.signature"].enrol(self.store_one, employee, face)

        event = self._crossing(self.device_one, face)
        self._resolve(event)

        self.assertFalse(event.counted)
        self.assertEqual(event.staff_id, employee)
        self.assertFalse(event.visitor_id)
        self.assertFalse(self.Visitor.search([("store_id", "=", self.store_one.id)]))

    def test_a_low_liveness_reading_is_not_trusted_when_required(self):
        self.store_one.write({
            "require_liveness": True, "liveness_min_score": 0.8})
        event = self._crossing(self.device_one, self.fake_vector(43))
        event.liveness_score = 0.2
        self._resolve(event)

        self.assertFalse(event.visitor_id, "a photo-grade reading built a visit")
        self.assertTrue(event.counted,
                        "the crossing itself must still count as a visitor")

    def test_liveness_is_ignored_when_the_store_does_not_ask_for_it(self):
        self.store_one.require_liveness = False
        event = self._crossing(self.device_one, self.fake_vector(45))
        event.liveness_score = 0.0
        self._resolve(event)
        self.assertTrue(event.visitor_id)

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------
    def test_signatures_expire_and_are_deleted(self):
        """Retention is the promise, so it gets a test."""
        self._resolve(self._crossing(self.device_one, self.fake_vector(51)))
        signature = self.Signature.search([("store_id", "=", self.store_one.id)])
        self.assertTrue(signature)

        signature.sudo().expires_at = fields.Datetime.now() - timedelta(minutes=1)
        self.Signature._cron_expire()
        self.assertFalse(signature.exists(),
                         "an expired face vector was still in the database")

    def test_an_expired_signature_is_not_matched_against(self):
        face = self.fake_vector(53)
        self._resolve(self._crossing(self.device_one, face))
        old = self.Signature.search([("store_id", "=", self.store_one.id)])
        old.sudo().expires_at = fields.Datetime.now() - timedelta(minutes=1)

        self._resolve(self._crossing(self.device_one, face))
        self.assertEqual(
            len(self.Signature.search([("store_id", "=", self.store_one.id)])), 2)

    def test_retention_window_is_per_store(self):
        self.store_one.reid_ttl_minutes = 30
        self.store_three.reid_ttl_minutes = 240
        self._resolve(self._crossing(self.device_one, self.fake_vector(55)))
        self._resolve(self._crossing(self.devices_three[0], self.fake_vector(55)))

        one = self.Signature.search([("store_id", "=", self.store_one.id)])
        three = self.Signature.search([("store_id", "=", self.store_three.id)])
        self.assertLess(one.expires_at, three.expires_at)

    def test_a_stale_visit_is_closed_without_inventing_an_exit_time(self):
        self.store_one.max_visit_minutes = 60
        old = fields.Datetime.now() - timedelta(hours=5)
        self._resolve(self._crossing(self.device_one, self.fake_vector(57),
                                     "in", when=old))
        visit = self.Visitor.search([("store_id", "=", self.store_one.id)])
        self.assertEqual(visit.state, "inside")

        self.Visitor._cron_close_stale()
        visit.invalidate_recordset()
        self.assertEqual(visit.state, "left")
        self.assertFalse(visit.exited_at,
                         "a fabricated exit time would poison dwell statistics")


@tagged("post_install", "-at_install")
class TestPurchaseUnits(AnalitixCase):

    def setUp(self):
        super().setUp()
        self.crypto = self.env["analitix.crypto"]
        self.Visitor = self.env["analitix.visitor"]
        self.Group = self.env["analitix.visit.group"]

    def _arrive(self, device, seed, when):
        event = self.make_event(
            device, "in", when=when,
            pending_embedding=self.crypto.encrypt_vector(
                self.crypto.normalize(self.fake_vector(seed))))
        job = self.env["analitix.job"].enqueue(
            "visitor_resolve", {"event_ids": event.ids}, store=device.store_id)
        job._run_one()
        event.invalidate_recordset()
        return event

    def test_people_arriving_together_are_one_unit(self):
        self.store_three.group_window_seconds = 3
        moment = fields.Datetime.now() - timedelta(minutes=5)
        first = self._arrive(self.devices_three[0], 61, moment)
        second = self._arrive(self.devices_three[0], 62,
                              moment + timedelta(seconds=1))

        self.assertTrue(first.visitor_id.visit_group_id)
        self.assertEqual(first.visitor_id.visit_group_id,
                         second.visitor_id.visit_group_id)
        self.assertEqual(first.visitor_id.visit_group_id.size, 2)
        self.assertEqual(first.visitor_id.visit_group_id.kind, "pair")

    def test_people_arriving_apart_are_separate_units(self):
        self.store_three.group_window_seconds = 2
        moment = fields.Datetime.now() - timedelta(minutes=5)
        first = self._arrive(self.devices_three[0], 71, moment)
        second = self._arrive(self.devices_three[0], 72,
                              moment + timedelta(minutes=1))
        self.assertNotEqual(first.visitor_id.visit_group_id,
                            second.visitor_id.visit_group_id)

    def test_different_doors_are_never_one_unit(self):
        """Two people at two entrances did not arrive together, however close."""
        self.store_three.group_window_seconds = 30
        moment = fields.Datetime.now() - timedelta(minutes=5)
        first = self._arrive(self.devices_three[0], 81, moment)
        second = self._arrive(self.devices_three[1], 82,
                              moment + timedelta(seconds=1))
        self.assertNotEqual(first.visitor_id.visit_group_id,
                            second.visitor_id.visit_group_id)

    def test_the_window_is_per_store(self):
        self.store_one.group_window_seconds = 1
        self.store_three.group_window_seconds = 20
        moment = fields.Datetime.now() - timedelta(minutes=5)

        a1 = self._arrive(self.device_one, 91, moment)
        a2 = self._arrive(self.device_one, 92, moment + timedelta(seconds=10))
        b1 = self._arrive(self.devices_three[0], 93, moment)
        b2 = self._arrive(self.devices_three[0], 94, moment + timedelta(seconds=10))

        self.assertNotEqual(a1.visitor_id.visit_group_id,
                            a2.visitor_id.visit_group_id)
        self.assertEqual(b1.visitor_id.visit_group_id,
                         b2.visitor_id.visit_group_id)

    def test_a_unit_stops_growing_at_the_configured_ceiling(self):
        """Without a ceiling a school group becomes a single 'customer'."""
        self.store_three.write({
            "group_window_seconds": 60, "group_max_size": 3})
        moment = fields.Datetime.now() - timedelta(minutes=5)
        events = [self._arrive(self.devices_three[0], 100 + n,
                               moment + timedelta(seconds=n))
                  for n in range(6)]
        groups = {e.visitor_id.visit_group_id for e in events}
        self.assertGreater(len(groups), 1)
        for group in groups:
            self.assertLessEqual(group.size, 3)

    def test_group_detection_can_be_switched_off(self):
        self.store_three.group_detection_enabled = False
        moment = fields.Datetime.now() - timedelta(minutes=5)
        event = self._arrive(self.devices_three[0], 121, moment)
        self.assertFalse(event.visitor_id.visit_group_id)


@tagged("post_install", "-at_install")
class TestDemographics(AnalitixCase):

    def setUp(self):
        super().setUp()
        self.Demographic = self.env["analitix.demographic"]
        self.store_one.demographics_enabled = True

    def test_an_age_is_stored_as_a_band(self):
        reading = self.Demographic.record(
            self.store_one, self.door_one,
            {"age": 31, "age_confidence": 0.9,
             "gender": "female", "gender_confidence": 0.88})
        self.assertEqual(reading.age_band, "25-34")

    def test_an_explicit_band_is_honoured(self):
        reading = self.Demographic.record(
            self.store_one, self.door_one,
            {"age_band": "55-64", "age_confidence": 0.7})
        self.assertEqual(reading.age_band, "55-64")

    def test_an_unknown_gender_is_a_legitimate_answer(self):
        reading = self.Demographic.record(
            self.store_one, self.door_one,
            {"age": 40, "age_confidence": 0.8, "gender": "wobble"})
        self.assertEqual(reading.gender, "unknown")

    def test_nothing_is_recorded_when_the_face_was_unreadable(self):
        """A crossing with no readable face is normal, not an error."""
        self.assertFalse(self.Demographic.record(
            self.store_one, self.door_one, {}))
        self.assertFalse(self.Demographic.record(
            self.store_one, self.door_one, None))

    def test_nothing_is_recorded_when_the_store_did_not_ask(self):
        self.store_one.demographics_enabled = False
        self.assertFalse(self.Demographic.record(
            self.store_one, self.door_one, {"age": 30, "age_confidence": 0.9}))

    def test_low_confidence_is_kept_but_flagged(self):
        """Dropping it would hide the uncertainty; averaging it would hide it worse."""
        self.store_one.demographic_min_confidence = 0.7
        reading = self.Demographic.record(
            self.store_one, self.door_one,
            {"age": 30, "age_confidence": 0.4,
             "gender": "male", "gender_confidence": 0.4})
        self.assertTrue(reading.exists())
        self.assertFalse(reading.reliable)

    def test_the_confidence_floor_is_per_store(self):
        self.store_one.demographic_min_confidence = 0.5
        self.store_three.demographics_enabled = True
        self.store_three.demographic_min_confidence = 0.95
        payload = {"age": 30, "age_confidence": 0.8,
                   "gender": "male", "gender_confidence": 0.8}
        self.assertTrue(self.Demographic.record(
            self.store_one, self.door_one, payload).reliable)
        self.assertFalse(self.Demographic.record(
            self.store_three, self.doors_three[0], payload).reliable)

    def test_a_reading_reaches_the_visit_it_belongs_to(self):
        crypto = self.env["analitix.crypto"]
        reading = self.Demographic.record(
            self.store_one, self.door_one,
            {"age": 22, "age_confidence": 0.9,
             "gender": "female", "gender_confidence": 0.9})
        event = self.make_event(
            self.device_one, "in",
            pending_embedding=crypto.encrypt_vector(
                crypto.normalize(self.fake_vector(131))),
            pending_demographic_id=reading.id)
        job = self.env["analitix.job"].enqueue(
            "visitor_resolve", {"event_ids": event.ids}, store=self.store_one)
        job._run_one()
        event.invalidate_recordset()

        self.assertEqual(event.visitor_id.demographic_id, reading)
        self.assertEqual(event.visitor_id.age_band, "18-24")
