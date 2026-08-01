# -*- coding: utf-8 -*-
"""Phase 3: zones, lost sales, displays, attribution and the discreet alert.

The alert tests carry the most weight here. "Discreet" is a promise made to the
*customer* standing in the shop, not a feature toggle, so the things it forbids
are tested as hard as the things it does.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests.common import tagged

from .common import AnalitixCase


class FloorCase(AnalitixCase):
    """Adds zones, a rota and a resolved visit to the base fixture."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Zone = cls.env["analitix.zone"]
        cls.Dwell = cls.env["analitix.zone.dwell"]
        cls.Alert = cls.env["analitix.alert"]
        cls.LostSale = cls.env["analitix.lost.sale"]
        cls.Poi = cls.env["analitix.poi"]

        cls.seller = cls.env["res.users"].with_context(
            no_reset_password=True).create({
                "name": "Rosa (floor)",
                "login": "analitix_seller@example.com",
                # Internal user, because a salesperson with an Odoo login is
                # one — and Discuss only reaches internal users.
                "group_ids": [(4, cls.env.ref("base.group_user").id),
                              (4, cls.env.ref("analitix.group_user").id)],
            })
        cls.manager = cls.env["res.users"].with_context(
            no_reset_password=True).create({
                "name": "Store manager",
                "login": "analitix_fallback@example.com",
                "group_ids": [(4, cls.env.ref("base.group_user").id),
                              (4, cls.env.ref("analitix.group_manager").id)],
            })
        cls.store_one.alert_fallback_user_id = cls.manager.id

        cls.rings = cls.Zone.create({
            "store_id": cls.store_one.id, "name": "Rings", "code": "R",
            "kind": "display", "engaged_seconds": 20,
            "lost_sale_seconds": 120, "alert_on_dwell": True,
        })
        cls.fitting = cls.Zone.create({
            "store_id": cls.store_one.id, "name": "Fitting", "code": "F",
            "kind": "fitting", "engaged_seconds": 20,
            "lost_sale_seconds": 120, "alert_on_dwell": False,
        })
        # Rosa covers the ring counter, all day, every day.
        cls.env["analitix.zone.vendor"].create({
            "zone_id": cls.rings.id, "user_id": cls.seller.id,
            "weekday": "all", "hour_from": 0.0, "hour_to": 24.0,
        })

    def make_visit(self, store=None, door=None):
        store = store or self.store_one
        return self.env["analitix.visitor"].create({
            "store_id": store.id,
            "door_id": (door or self.door_one).id,
            "entered_at": fields.Datetime.now() - timedelta(minutes=10),
            "state": "inside",
        })


@tagged("post_install", "-at_install")
class TestDiscreetAlert(FloorCase):

    def test_the_alert_reaches_the_person_covering_that_zone(self):
        alert = self.Alert.raise_alert(
            self.store_one, "lost_sale", "Someone is waiting", zone=self.rings)
        self.assertEqual(alert.user_id, self.seller)
        self.assertFalse(alert.was_fallback)

    def test_an_uncovered_zone_escalates_instead_of_evaporating(self):
        alert = self.Alert.raise_alert(
            self.store_one, "lost_sale", "Someone is waiting", zone=self.fitting)
        self.assertEqual(alert.user_id, self.manager)
        self.assertTrue(alert.was_fallback,
                        "an escalation must be visible, or the rota never gets fixed")

    def test_coverage_respects_the_shift_hours(self):
        """Whoever covers the counter at 11:00 is not whoever covers it at 19:00."""
        self.env["analitix.zone.vendor"].search(
            [("zone_id", "=", self.rings.id)]).unlink()
        morning = self.env["res.users"].with_context(
            no_reset_password=True).create({
                "name": "Morning shift", "login": "analitix_am@example.com"})
        self.env["analitix.zone.vendor"].create({
            "zone_id": self.rings.id, "user_id": morning.id,
            "weekday": "all", "hour_from": 8.0, "hour_to": 14.0,
        })

        Coverage = self.env["analitix.zone.vendor"]
        self.store_one.tz = "UTC"
        at_ten = fields.Datetime.now().replace(hour=10, minute=0, second=0)
        at_twenty = fields.Datetime.now().replace(hour=20, minute=0, second=0)
        self.assertIn(morning, Coverage._covering(self.rings, at_ten))
        self.assertNotIn(morning, Coverage._covering(self.rings, at_twenty))

    def test_the_non_discreet_channels_are_off_by_default(self):
        """The shop owner may switch them on; nobody gets them by accident.

        The original brief excluded a chime and a screen outright. The owner
        asked for the choice, so the choice exists — but a store that never
        opens this screen keeps the discreet behaviour, which is the part that
        must not depend on anyone reading the documentation.
        """
        fresh = self.env["analitix.store"].create({
            "name": "Defaults check", "code": "DEF", "tz": "UTC",
            "company_id": self.env.company.id, "match_mode": "company",
        })
        self.assertTrue(fresh.alert_use_app)
        self.assertFalse(fresh.alert_use_sound)
        self.assertFalse(fresh.alert_use_screen)
        self.assertFalse(fresh.alert_use_discuss)
        self.assertFalse(fresh.alert_use_whatsapp)

    def test_channels_combine_rather_than_exclude_each_other(self):
        """A store may want the app and the chat at once, which the old single
        selector made impossible."""
        self.store_one.write({
            "alert_use_app": True, "alert_use_discuss": True})
        alert = self.Alert.raise_alert(
            self.store_one, "lost_sale", "Someone is waiting", zone=self.rings)
        self.assertTrue(alert.sent_app)
        self.assertTrue(alert.sent_discuss)
        self.assertTrue(alert.delivered)
        self.assertIn("app", alert.channel_summary)
        self.assertIn("chat", alert.channel_summary)

    def test_discuss_delivers_a_private_message(self):
        """One-to-one, so the rest of the floor never sees it."""
        self.store_one.write({
            "alert_use_app": False, "alert_use_discuss": True})
        alert = self.Alert.raise_alert(
            self.store_one, "lost_sale", "Ring counter waiting", zone=self.rings)

        self.assertTrue(alert.sent_discuss)
        message = self.env["mail.message"].search([
            ("model", "=", "discuss.channel"),
            ("body", "ilike", "Ring counter waiting"),
        ], limit=1)
        self.assertTrue(message, "no Discuss message was posted")
        channel = self.env["discuss.channel"].browse(message.res_id)
        self.assertIn(self.seller.partner_id, channel.channel_partner_ids)

    def test_the_chime_flag_is_recorded_so_it_can_be_audited_later(self):
        self.store_one.write({"alert_use_app": True, "alert_use_sound": True})
        alert = self.Alert.raise_alert(
            self.store_one, "lost_sale", "Waiting", zone=self.rings)
        self.assertTrue(alert.sent_sound)
        self.assertIn("chime", alert.channel_summary)

    def test_the_screen_channel_needs_a_display_group_on_the_zone(self):
        """Switched on but unmapped delivers nothing, and says so."""
        self.store_one.write({"alert_use_app": False, "alert_use_screen": True})
        self.assertFalse(self.rings.screen_group_ref)
        alert = self.Alert.raise_alert(
            self.store_one, "lost_sale", "Waiting", zone=self.rings)
        self.assertFalse(alert.sent_screen)
        self.assertFalse(alert.delivered,
                         "an undelivered alert must not claim it was delivered")

    def test_a_second_nudge_inside_the_cooldown_is_suppressed(self):
        """Buzz someone every ninety seconds and they stop reading the alerts."""
        self.store_one.alert_cooldown_minutes = 10
        first = self.Alert.raise_alert(
            self.store_one, "lost_sale", "One", zone=self.rings)
        second = self.Alert.raise_alert(
            self.store_one, "lost_sale", "Two", zone=self.rings)
        self.assertTrue(first)
        self.assertFalse(second)

    def test_the_cooldown_does_not_suppress_a_different_kind(self):
        self.store_one.alert_cooldown_minutes = 10
        self.Alert.raise_alert(self.store_one, "lost_sale", "One", zone=self.rings)
        other = self.Alert.raise_alert(
            self.store_one, "anomaly", "Two", zone=self.rings)
        self.assertTrue(other)

    def test_acknowledging_records_the_response_time(self):
        alert = self.Alert.raise_alert(
            self.store_one, "lost_sale", "Waiting", zone=self.rings)
        alert.sudo().sent_at = fields.Datetime.now() - timedelta(seconds=45)
        alert.action_acknowledge()
        self.assertTrue(alert.acknowledged)
        self.assertEqual(alert.outcome, "attended")
        self.assertGreaterEqual(alert.response_seconds, 40)

    def test_an_ignored_alert_becomes_evidence(self):
        """A report that only saw the alerts that went well would be useless."""
        self.store_one.alert_missed_after_minutes = 5
        alert = self.Alert.raise_alert(
            self.store_one, "lost_sale", "Waiting", zone=self.rings)
        alert.sudo().sent_at = fields.Datetime.now() - timedelta(minutes=30)

        self.Alert._cron_mark_missed()
        alert.invalidate_recordset()
        self.assertEqual(alert.outcome, "missed")

    def test_raising_an_alert_never_raises(self):
        """The alert path hangs off counting; it must not be able to break it."""
        store = self.store_one
        store.alert_fallback_user_id = False
        self.env["analitix.zone.vendor"].search(
            [("zone_id", "=", self.rings.id)]).unlink()
        alert = self.Alert.raise_alert(store, "lost_sale", "Nobody home",
                                       zone=self.rings)
        self.assertTrue(alert, "the alert must still be recorded")
        self.assertFalse(alert.user_id)
        self.assertFalse(alert.delivered)


@tagged("post_install", "-at_install")
class TestZoneDwellAndLostSales(FloorCase):

    def test_dwell_is_upserted_not_appended(self):
        """The edge reports a running total; appending would spam the floor."""
        visit = self.make_visit()
        when = fields.Datetime.now() - timedelta(minutes=5)
        self.Dwell.record(visit, self.rings, when, 30)
        self.Dwell.record(visit, self.rings, when, 90)
        rows = self.Dwell.search(
            [("visitor_id", "=", visit.id), ("zone_id", "=", self.rings.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.seconds, 90)

    def test_a_short_pass_is_recorded_but_not_engagement(self):
        visit = self.make_visit()
        dwell = self.Dwell.record(
            visit, self.rings, fields.Datetime.now(), 5)
        self.assertTrue(dwell.exists())
        self.assertFalse(dwell.engaged,
                         "a corridor would otherwise report everyone as engaged")

    def test_a_long_unserved_dwell_raises_a_lost_sale_and_a_nudge(self):
        visit = self.make_visit()
        dwell = self.Dwell.record(
            visit, self.rings, fields.Datetime.now() - timedelta(minutes=5), 300)
        record = self.LostSale._evaluate_dwell(dwell)

        self.assertTrue(record)
        self.assertEqual(record.state, "open")
        self.assertTrue(record.alert_id)
        self.assertEqual(record.alert_id.user_id, self.seller)

    def test_a_served_customer_is_not_a_lost_sale(self):
        visit = self.make_visit()
        dwell = self.Dwell.record(
            visit, self.rings, fields.Datetime.now(), 300, served=True)
        self.assertFalse(self.LostSale._evaluate_dwell(dwell))

    def test_a_short_dwell_is_not_a_lost_sale(self):
        visit = self.make_visit()
        dwell = self.Dwell.record(visit, self.rings, fields.Datetime.now(), 30)
        self.assertFalse(self.LostSale._evaluate_dwell(dwell))

    def test_a_zone_that_opted_out_never_nudges(self):
        """Lingering in a fitting room is the activity, not a problem."""
        visit = self.make_visit()
        dwell = self.Dwell.record(visit, self.fitting, fields.Datetime.now(), 600)
        self.assertFalse(self.LostSale._evaluate_dwell(dwell))

    def test_the_same_dwell_only_ever_raises_once(self):
        visit = self.make_visit()
        when = fields.Datetime.now() - timedelta(minutes=5)
        dwell = self.Dwell.record(visit, self.rings, when, 300)
        self.assertTrue(self.LostSale._evaluate_dwell(dwell))
        self.Dwell.record(visit, self.rings, when, 400)
        dwell.invalidate_recordset()
        self.assertFalse(self.LostSale._evaluate_dwell(dwell))

    def test_thresholds_are_per_zone(self):
        patient = self.Zone.create({
            "store_id": self.store_one.id, "name": "Browse", "code": "B",
            "engaged_seconds": 20, "lost_sale_seconds": 900,
        })
        visit = self.make_visit()
        quick = self.Dwell.record(visit, self.rings, fields.Datetime.now(), 300)
        slow = self.Dwell.record(visit, patient, fields.Datetime.now(), 300)
        self.assertTrue(self.LostSale._evaluate_dwell(quick))
        self.assertFalse(self.LostSale._evaluate_dwell(slow))

    def test_a_visit_that_buys_is_marked_rescued(self):
        visit = self.make_visit()
        dwell = self.Dwell.record(
            visit, self.rings, fields.Datetime.now() - timedelta(minutes=5), 300)
        record = self.LostSale._evaluate_dwell(dwell)

        order = self._make_order(self.store_one)
        self.env["analitix.sale.match"].sudo().create({
            "store_id": self.store_one.id,
            "visitor_id": visit.id,
            "pos_order_id": order.id,
            "method": "face",
        })
        record._settle()

        self.assertEqual(record.state, "rescued")
        self.assertEqual(record.alert_id.outcome, "sold")

    def test_a_visit_that_leaves_empty_handed_is_marked_lost(self):
        visit = self.make_visit()
        dwell = self.Dwell.record(
            visit, self.rings, fields.Datetime.now() - timedelta(minutes=5), 300)
        record = self.LostSale._evaluate_dwell(dwell)
        visit.write({"state": "left", "exited_at": fields.Datetime.now()})
        record._settle()
        self.assertEqual(record.state, "lost")

    def test_no_lead_is_created_for_an_anonymous_visitor(self):
        """A lead with no name and no phone buries the real ones."""
        self.store_one.lost_sale_create_lead = True
        visit = self.make_visit()
        dwell = self.Dwell.record(
            visit, self.rings, fields.Datetime.now() - timedelta(minutes=5), 300)
        record = self.LostSale._evaluate_dwell(dwell)
        visit.write({"state": "left", "exited_at": fields.Datetime.now()})
        record._settle()
        self.assertFalse(record.lead_id)

    def test_a_lead_is_created_for_an_identified_customer(self):
        self.store_one.lost_sale_create_lead = True
        partner = self.env["res.partner"].create({"name": "Known customer"})
        crypto = self.env["analitix.crypto"]
        signature = self.env["analitix.face.signature"].sudo().create({
            "reference": "TEST-LEAD-1",
            "store_id": self.store_one.id,
            "embedding": crypto.encrypt_vector(self.fake_vector(5)),
            "embedding_dim": 32,
            "expires_at": fields.Datetime.now() + timedelta(days=1),
            "partner_id": partner.id,
            "identified": True,
        })
        visit = self.make_visit()
        visit.signature_id = signature.id
        dwell = self.Dwell.record(
            visit, self.rings, fields.Datetime.now() - timedelta(minutes=5), 300)
        record = self.LostSale._evaluate_dwell(dwell)
        visit.write({"state": "left", "exited_at": fields.Datetime.now()})
        record._settle()

        self.assertTrue(record.lead_id)
        self.assertEqual(record.lead_id.partner_id, partner)

    def _make_order(self, store):
        config = self.env["pos.config"].create({
            "name": "Floor register %s" % store.code,
            "company_id": store.company_id.id,
        })
        config.with_user(self.env.user).open_ui()
        session = self.env["pos.session"].search(
            [("config_id", "=", config.id)], limit=1)
        product = self.env["product.product"].create({
            "name": "Ring", "available_in_pos": True, "list_price": 100.0,
            "type": "consu",
        })
        return self.env["pos.order"].create({
            "session_id": session.id,
            "company_id": store.company_id.id,
            "date_order": fields.Datetime.now(),
            "amount_tax": 0.0, "amount_total": 100.0,
            "amount_paid": 100.0, "amount_return": 0.0,
            "state": "paid",
            "lines": [(0, 0, {
                "product_id": product.id, "qty": 1, "price_unit": 100.0,
                "price_subtotal": 100.0, "price_subtotal_incl": 100.0,
            })],
        })


@tagged("post_install", "-at_install")
class TestIdentification(FloorCase):

    def setUp(self):
        super().setUp()
        self.crypto = self.env["analitix.crypto"]
        self.Signature = self.env["analitix.face.signature"]
        self.Match = self.env["analitix.sale.match"]
        self.partner = self.env["res.partner"].create({"name": "Gustavo"})

    def _signature(self, seed=61):
        return self.Signature.sudo().create({
            "reference": "TEST-ID-%s" % seed,
            "store_id": self.store_one.id,
            "embedding": self.crypto.encrypt_vector(self.fake_vector(seed)),
            "embedding_dim": 32,
            "expires_at": fields.Datetime.now() + timedelta(hours=1),
            "liveness_score": 0.95,
        })

    def test_identification_is_off_unless_the_store_asks(self):
        """A shop that only bought the analytics must not acquire a face index."""
        self.assertFalse(self.store_one.identify_customers)
        signature = self._signature()
        visit = self.make_visit()
        visit.signature_id = signature.id

        self.Match._maybe_identify(self.store_one, visit, self.partner)
        signature.invalidate_recordset()
        self.assertFalse(signature.identified)
        self.assertFalse(signature.partner_id)

    def test_a_customer_who_gave_their_details_can_be_identified(self):
        self.store_one.identify_customers = True
        signature = self._signature()
        visit = self.make_visit()
        visit.signature_id = signature.id

        self.assertTrue(
            self.Match._maybe_identify(self.store_one, visit, self.partner))
        signature.invalidate_recordset()
        self.assertTrue(signature.identified)
        self.assertEqual(signature.partner_id, self.partner)

    def test_identification_outlives_the_anonymous_window_but_not_forever(self):
        self.store_one.write({
            "identify_customers": True,
            "reid_ttl_minutes": 60,
            "identified_ttl_days": 30,
        })
        signature = self._signature()
        visit = self.make_visit()
        visit.signature_id = signature.id
        anonymous_expiry = signature.expires_at

        self.Match._maybe_identify(self.store_one, visit, self.partner)
        signature.invalidate_recordset()
        self.assertGreater(signature.expires_at, anonymous_expiry)
        self.assertLess(
            signature.expires_at,
            fields.Datetime.now() + timedelta(days=31),
            "an identified signature must still expire")

    def test_a_photo_grade_reading_cannot_create_an_identity(self):
        """Exactly the decision task 984 says liveness has to guard."""
        self.store_one.write({
            "identify_customers": True,
            "require_liveness": True,
            "liveness_min_score": 0.8,
        })
        signature = self._signature()
        signature.sudo().liveness_score = 0.1
        visit = self.make_visit()
        visit.signature_id = signature.id

        self.assertFalse(
            self.Match._maybe_identify(self.store_one, visit, self.partner))
        signature.invalidate_recordset()
        self.assertFalse(signature.identified)

    def test_identifying_a_customer_is_audited(self):
        self.store_one.identify_customers = True
        signature = self._signature()
        visit = self.make_visit()
        visit.signature_id = signature.id
        self.Match._maybe_identify(self.store_one, visit, self.partner)

        self.assertTrue(self.env["analitix.audit.log"].search_count([
            ("action", "=", "elevated"),
            ("model_name", "=", "analitix.face.signature"),
        ]))

    def test_a_known_customer_arriving_nudges_the_salesperson(self):
        self.store_one.write({
            "identify_customers": True, "greet_known_customers": True})
        self.Zone.create({
            "store_id": self.store_one.id, "name": "Door", "code": "D",
            "kind": "entrance",
        })
        signature = self._signature()
        signature.sudo().write({
            "partner_id": self.partner.id, "identified": True})
        visit = self.make_visit()

        self.Signature._greet_if_known(self.store_one, signature, visit)
        alert = self.env["analitix.alert"].search([
            ("kind", "=", "known_customer"),
            ("partner_id", "=", self.partner.id),
        ], limit=1)
        self.assertTrue(alert)
        self.assertIn("Gustavo", alert.summary)

    def test_an_anonymous_visitor_produces_no_greeting(self):
        self.store_one.write({
            "identify_customers": True, "greet_known_customers": True})
        signature = self._signature()
        visit = self.make_visit()
        self.assertFalse(
            self.Signature._greet_if_known(self.store_one, signature, visit))


@tagged("post_install", "-at_install")
class TestDisplaysAndBehaviour(FloorCase):

    def test_a_stop_shorter_than_the_threshold_is_not_a_stop(self):
        poi = self.Poi.create({
            "zone_id": self.rings.id, "name": "Showcase", "code": "SC",
            "stop_seconds": 10,
        })
        visit = self.make_visit()
        Attention = self.env["analitix.poi.attention"]
        self.assertFalse(
            Attention.record(visit, poi, fields.Datetime.now(), 3))
        self.assertTrue(
            Attention.record(visit, poi, fields.Datetime.now(), 30))

    def test_attention_is_upserted_like_dwell(self):
        poi = self.Poi.create({
            "zone_id": self.rings.id, "name": "Showcase", "code": "SC2",
            "stop_seconds": 5,
        })
        visit = self.make_visit()
        when = fields.Datetime.now()
        Attention = self.env["analitix.poi.attention"]
        Attention.record(visit, poi, when, 10)
        Attention.record(visit, poi, when, 40)
        rows = Attention.search([("poi_id", "=", poi.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.seconds, 40)

    def test_repeated_re_entries_are_flagged_as_behaviour(self):
        self.store_one.write({
            "anomaly_detection_enabled": True, "anomaly_reentry_count": 3})
        visit = self.make_visit()
        visit.re_entry_count = 4

        self.env["analitix.anomaly.event"]._scan_visit(self.store_one, visit)
        signal = self.env["analitix.anomaly.event"].search(
            [("visitor_id", "=", visit.id), ("kind", "=", "repeat_entry")])
        self.assertTrue(signal)
        self.assertTrue(signal.alert_id)

    def test_behaviour_signals_are_off_unless_the_store_asks(self):
        self.store_one.anomaly_detection_enabled = False
        visit = self.make_visit()
        visit.re_entry_count = 9
        self.env["analitix.anomaly.event"]._scan_visit(self.store_one, visit)
        self.assertFalse(self.env["analitix.anomaly.event"].search(
            [("visitor_id", "=", visit.id)]))

    def test_the_same_signal_is_only_raised_once_per_visit(self):
        self.store_one.write({
            "anomaly_detection_enabled": True, "anomaly_reentry_count": 2})
        visit = self.make_visit()
        visit.re_entry_count = 5
        Anomaly = self.env["analitix.anomaly.event"]
        Anomaly._scan_visit(self.store_one, visit)
        Anomaly._scan_visit(self.store_one, visit)
        self.assertEqual(len(Anomaly.search(
            [("visitor_id", "=", visit.id), ("kind", "=", "repeat_entry")])), 1)

    def test_a_behaviour_signal_carries_no_identity(self):
        """It is about a pattern, not a person, and the schema says so."""
        Anomaly = self.env["analitix.anomaly.event"]
        self.assertNotIn("partner_id", Anomaly._fields)
        self.assertNotIn("name", Anomaly._fields)
        self.assertNotIn("embedding", Anomaly._fields)
