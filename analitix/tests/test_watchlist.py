# -*- coding: utf-8 -*-
"""Phase 5: the watch list.

This is the only feature in Analitix that names a specific person, so the tests
here are weighted toward what it must *refuse* to do. A watch list that works
is not the achievement — a watch list that cannot be switched on by one angry
person, cannot act on a photograph, cannot outlive its own review date and
cannot be read without leaving a trace is.

Both store shapes appear, as the master instruction requires: the one-door
boutique carries the working list, and the three-door mall unit is used to
prove that a match in one store never reaches the other.
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged

from .common import AnalitixCase


class WatchCase(AnalitixCase):
    """Two authorised people, a store with the feature on, and one entry."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Watch = cls.env["analitix.watch.person"]
        cls.Match = cls.env["analitix.watch.match"]
        cls.security_group = cls.env.ref("analitix.group_security")

        cls.officer = cls.env["res.users"].with_context(
            no_reset_password=True).create({
                "name": "Security officer",
                "login": "analitix_officer@example.com",
                "group_ids": [(4, cls.env.ref("base.group_user").id),
                              (4, cls.security_group.id)],
            })
        cls.second_officer = cls.env["res.users"].with_context(
            no_reset_password=True).create({
                "name": "Second officer",
                "login": "analitix_officer2@example.com",
                "group_ids": [(4, cls.env.ref("base.group_user").id),
                              (4, cls.security_group.id)],
            })
        # A store manager, who deliberately does NOT hold the security role.
        cls.shop_manager = cls.env["res.users"].with_context(
            no_reset_password=True).create({
                "name": "Shop manager",
                "login": "analitix_shopmgr@example.com",
                "group_ids": [(4, cls.env.ref("base.group_user").id),
                              (4, cls.env.ref("analitix.group_manager").id)],
            })

        cls.store_one.write({
            "watchlist_enabled": True,
            "watchlist_user_ids": [(6, 0, [cls.officer.id])],
            "require_liveness": False,
        })

    def _entry(self, store=None, seed=7, created_by=None, **extra):
        """A confirmed, active entry with a signature attached."""
        store = store or self.store_one
        user = created_by or self.officer
        vals = {
            "store_id": store.id,
            "display_label": "Test entry",
            "reason": "Documented incident during testing.",
            "incident_date": fields.Date.context_today(self.env.user),
        }
        vals.update(extra)
        entry = self.Watch.with_user(user).create(vals)
        self.Watch.enrol(entry.sudo(), self.fake_vector(seed))
        return entry.sudo()


@tagged("post_install", "-at_install")
class TestWatchlistControl(WatchCase):
    """The controls around putting a name on the list."""

    def test_a_new_entry_is_inert(self):
        entry = self._entry()
        self.assertEqual(entry.state, "draft")
        found = self.Watch.check(
            self.store_one, self.fake_vector(7), liveness=1.0)
        self.assertFalse(
            found, "a draft entry recognised somebody before anyone agreed to it")

    def test_the_author_cannot_confirm_their_own_entry(self):
        """The whole point of the double control.

        A rule one determined person can satisfy alone is not a control, it is
        a formality.
        """
        entry = self._entry(created_by=self.officer)
        with self.assertRaises(UserError):
            entry.with_user(self.officer).action_confirm()
        self.assertEqual(entry.state, "draft")

    def test_a_second_officer_makes_it_live(self):
        entry = self._entry(created_by=self.officer)
        entry.with_user(self.second_officer).action_confirm()
        entry.invalidate_recordset()
        self.assertEqual(entry.state, "active")
        self.assertEqual(entry.confirmed_by_id, self.second_officer)
        self.assertTrue(entry.confirmed_on)

    def test_an_entry_without_a_signature_cannot_be_confirmed(self):
        """It would match nothing, so confirming it only creates the illusion
        of a control that is running."""
        entry = self.Watch.with_user(self.officer).create({
            "store_id": self.store_one.id,
            "display_label": "No signature",
            "reason": "Nothing enrolled.",
            "incident_date": fields.Date.context_today(self.env.user),
        })
        with self.assertRaises(UserError):
            entry.with_user(self.second_officer).action_confirm()

    def test_nothing_creates_an_entry_automatically(self):
        """No ingest path may ever add somebody to this list.

        Proved by running a full resolve over a crossing with the feature on
        and asserting the list is still empty — the guarantee is about the
        pipeline's behaviour, not about anyone's intentions.
        """
        before = self.Watch.search_count([])
        event = self.make_event(self.device_one, "in")
        event.pending_embedding = self.env["analitix.crypto"].encrypt_vector(
            self.fake_vector(41))
        self.env["analitix.face.signature"]._run_visitor_resolve(
            self._job_for(event))
        self.assertEqual(self.Watch.search_count([]), before,
                         "the ingest pipeline created a watch-list entry")

    def _job_for(self, event):
        return self.env["analitix.job"].create({
            "kind": "visitor_resolve",
            "store_id": event.store_id.id,
            "payload": '{"event_ids": [%d]}' % event.id,
        })


@tagged("post_install", "-at_install")
class TestWatchlistMatching(WatchCase):
    """What it takes to trigger a match, and what a match does."""

    def setUp(self):
        super().setUp()
        self.entry = self._entry(seed=7, created_by=self.officer)
        self.entry.with_user(self.second_officer).action_confirm()

    def test_the_same_face_matches(self):
        found = self.Watch.check(
            self.store_one, self.fake_vector(7), liveness=1.0)
        self.assertEqual(found, self.entry)

    def test_a_different_face_does_not(self):
        found = self.Watch.check(
            self.store_one, self.fake_vector(91), liveness=1.0)
        self.assertFalse(found)

    def test_the_threshold_is_stricter_than_re_identification(self):
        """A near miss that would happily pass as the same visitor must not be
        enough to name somebody."""
        self.assertGreater(self.store_one.watchlist_threshold,
                           self.store_one.reid_threshold)
        with self.assertRaises(ValidationError):
            self.store_one.watchlist_threshold = (
                self.store_one.reid_threshold - 0.05)

    def test_a_low_liveness_reading_is_never_checked(self):
        """A photograph held up to a camera must not be able to put a real
        person under suspicion."""
        found = self.Watch.check(
            self.store_one, self.fake_vector(7),
            liveness=self.store_one.watchlist_min_liveness - 0.2)
        self.assertFalse(found)
        self.assertFalse(self.Match.search([("person_id", "=", self.entry.id)]))

    def test_the_feature_switch_really_switches_it_off(self):
        self.store_one.watchlist_enabled = False
        self.assertFalse(self.Watch.check(
            self.store_one, self.fake_vector(7), liveness=1.0))

    def test_an_expired_entry_stops_matching(self):
        self.entry.write({
            "review_on": fields.Date.subtract(fields.Date.today(), days=40),
            "expires_on": fields.Date.subtract(fields.Date.today(), days=10),
        })
        self.assertFalse(self.Watch.check(
            self.store_one, self.fake_vector(7), liveness=1.0))

    def test_a_match_never_crosses_store_boundaries(self):
        """The mall unit has its own list, and the boutique's entry is not on
        it — on a shared instance that is the difference between a tenant
        boundary and a suggestion."""
        self.store_three.write({
            "watchlist_enabled": True,
            "watchlist_user_ids": [(6, 0, [self.officer.id])],
        })
        found = self.Watch.check(
            self.store_three, self.fake_vector(7), liveness=1.0)
        self.assertFalse(found)

    def test_a_match_alerts_only_the_named_group(self):
        self.Watch.check(self.store_one, self.fake_vector(7), liveness=1.0)
        alerts = self.env["analitix.alert"].search([
            ("store_id", "=", self.store_one.id), ("kind", "=", "watchlist")])
        self.assertTrue(alerts)
        self.assertEqual(alerts.mapped("user_id"), self.officer,
                         "a watch-list match reached somebody outside the "
                         "configured group")

    def test_a_match_never_reaches_a_screen(self):
        """Even with the store's screen channel switched on.

        The screen is read by whoever is standing in front of it, which for a
        watch-list match is the person it is about.
        """
        self.store_one.write({"alert_use_screen": True, "signage_enabled": True})
        self.Watch.check(self.store_one, self.fake_vector(7), liveness=1.0)
        alert = self.env["analitix.alert"].search(
            [("kind", "=", "watchlist")], limit=1)
        self.assertTrue(alert)
        self.assertFalse(alert.sent_screen,
                         "a watch-list match was put on a public screen")
        self.assertFalse(self.env["analitix.signage.event"].search(
            [("store_id", "=", self.store_one.id)]),
            "a watch-list match drove the signage engine")

    def test_a_match_takes_no_automatic_action(self):
        """It records a sighting and tells a person. Nothing else — no lead, no
        loyalty change, no ticket, no state change on the visit."""
        lead_model = self.env.get("crm.lead")
        leads_before = lead_model.search_count([]) if lead_model is not None else 0
        self.Watch.check(self.store_one, self.fake_vector(7), liveness=1.0)
        if lead_model is not None:
            self.assertEqual(lead_model.search_count([]), leads_before)
        match = self.Match.search([("person_id", "=", self.entry.id)])
        self.assertEqual(len(match), 1)
        self.assertEqual(match.outcome, "pending",
                         "the system decided the outcome instead of a person")

    def test_a_store_with_nobody_to_tell_still_records_the_match(self):
        """Silently telling nobody would be the worst of both worlds: the
        recognition happened, and no one can see that it did."""
        self.store_one.watchlist_user_ids = [(5, 0, 0)]
        self.Watch.check(self.store_one, self.fake_vector(7), liveness=1.0)
        self.assertTrue(self.Match.search([("person_id", "=", self.entry.id)]))

    def test_a_real_crossing_reaches_the_list(self):
        """End to end, through the ingest pipeline rather than by calling the
        check directly — the wiring is the part that silently stops working."""
        # The liveness score has to come from the edge, as it would in
        # production: a crossing that carries none is deliberately never
        # checked against the list at all.
        event = self.make_event(self.device_one, "in", liveness_score=0.95)
        event.pending_embedding = self.env["analitix.crypto"].encrypt_vector(
            self.fake_vector(7))
        job = self.env["analitix.job"].create({
            "kind": "visitor_resolve",
            "store_id": self.store_one.id,
            "payload": '{"event_ids": [%d]}' % event.id,
        })
        self.env["analitix.face.signature"]._run_visitor_resolve(job)
        match = self.Match.search([("person_id", "=", self.entry.id)])
        self.assertEqual(len(match), 1,
                         "a crossing never reached the watch list")
        self.assertTrue(match.visitor_id,
                        "the match was not tied to the visit it came from")

    def test_a_crossing_with_no_liveness_reading_is_not_checked(self):
        """The counterpart of the test above, and the more important half.

        A camera that reports no liveness sends zero, so a store whose edge
        agents do not do liveness matches nothing at all. That is the safe way
        round, and it is a behaviour worth pinning down rather than leaving to
        be rediscovered as 'the watch list does not work'.
        """
        event = self.make_event(self.device_one, "in")
        event.pending_embedding = self.env["analitix.crypto"].encrypt_vector(
            self.fake_vector(7))
        job = self.env["analitix.job"].create({
            "kind": "visitor_resolve",
            "store_id": self.store_one.id,
            "payload": '{"event_ids": [%d]}' % event.id,
        })
        self.env["analitix.face.signature"]._run_visitor_resolve(job)
        self.assertFalse(self.Match.search([("person_id", "=", self.entry.id)]))

    def test_a_false_positive_can_be_recorded(self):
        self.Watch.check(self.store_one, self.fake_vector(7), liveness=1.0)
        match = self.Match.search([("person_id", "=", self.entry.id)], limit=1)
        match.with_user(self.officer).action_wrong_person()
        match.invalidate_recordset()
        self.assertEqual(match.outcome, "wrong_person")


@tagged("post_install", "-at_install")
class TestWatchlistExpiry(WatchCase):

    def test_a_new_entry_gets_dates_from_the_stores_policy(self):
        self.store_one.write({
            "watchlist_review_days": 30, "watchlist_expiry_days": 120})
        entry = self._entry()
        today = fields.Date.today()
        self.assertEqual(entry.review_on, fields.Date.add(today, days=30))
        self.assertEqual(entry.expires_on, fields.Date.add(today, days=120))

    def test_no_entry_can_outrun_the_stores_ceiling(self):
        entry = self._entry()
        with self.assertRaises(ValidationError):
            entry.expires_on = fields.Date.add(
                fields.Date.today(),
                days=self.store_one.watchlist_max_days + 30)

    def test_the_cron_expires_what_is_past_its_date(self):
        entry = self._entry(created_by=self.officer)
        entry.with_user(self.second_officer).action_confirm()
        entry.write({
            "review_on": fields.Date.subtract(fields.Date.today(), days=30),
            "expires_on": fields.Date.subtract(fields.Date.today(), days=1),
        })
        self.Watch._cron_expire()
        entry.invalidate_recordset()
        self.assertEqual(entry.state, "expired")

    def test_an_expired_entry_is_not_deleted(self):
        """The record of why somebody was listed outlives the listing — that is
        what makes the trail auditable rather than self-cleaning."""
        entry = self._entry(created_by=self.officer)
        entry.with_user(self.second_officer).action_confirm()
        entry.write({
            "review_on": fields.Date.subtract(fields.Date.today(), days=20),
            "expires_on": fields.Date.subtract(fields.Date.today(), days=1),
        })
        self.Watch._cron_expire()
        self.assertTrue(entry.exists())
        self.assertTrue(entry.reason)

    def test_a_due_entry_raises_a_review_for_a_person(self):
        entry = self._entry(created_by=self.officer)
        entry.with_user(self.second_officer).action_confirm()
        entry.write({"review_on": fields.Date.today()})
        self.Watch._cron_expire()
        activity = self.env["mail.activity"].search([
            ("res_model", "=", "analitix.watch.person"),
            ("res_id", "=", entry.id)])
        self.assertTrue(activity, "an entry came due and nobody was asked")

    def test_extending_is_recorded_and_bounded(self):
        entry = self._entry(created_by=self.officer)
        entry.with_user(self.second_officer).action_confirm()
        entry.write({
            "review_on": fields.Date.subtract(fields.Date.today(), days=20),
            "expires_on": fields.Date.subtract(fields.Date.today(), days=1),
        })
        self.Watch._cron_expire()
        entry.with_user(self.second_officer).action_extend()
        entry.invalidate_recordset()
        self.assertEqual(entry.state, "active")
        self.assertEqual(
            entry.expires_on,
            fields.Date.add(fields.Date.today(),
                            days=self.store_one.watchlist_expiry_days))


@tagged("post_install", "-at_install")
class TestWatchlistAccess(WatchCase):
    """Who may see this, and what looking leaves behind."""

    def test_a_store_manager_cannot_read_the_watch_list(self):
        """Presence on a watch list is not commercial information.

        The manager here holds the highest ordinary Analitix role and still has
        no way in — the security role is deliberately outside that ladder.
        """
        entry = self._entry()
        self.assertNotIn(self.security_group,
                         self.shop_manager.group_ids)
        with self.assertRaises(AccessError):
            self.Watch.with_user(self.shop_manager).browse(entry.id).read(
                ["display_label"])

    def test_nobody_can_delete_an_entry(self):
        """Removal is a state change with a name attached to it, not an
        erasure. An audit trail somebody can tidy away is not a trail."""
        entry = self._entry()
        with self.assertRaises(AccessError):
            entry.with_user(self.officer).unlink()

    def test_reading_the_list_is_audited(self):
        """Odoo's chatter answers who *changed* an entry. The question that
        matters for a list of people is who went through it."""
        entry = self._entry()
        Audit = self.env["analitix.audit.log"]
        before = Audit.search_count([("model_name", "=", "analitix.watch.person")])
        self.Watch.with_user(self.officer).browse(entry.id).read(
            ["display_label", "reason"])
        self.assertGreater(
            Audit.search_count([("model_name", "=", "analitix.watch.person")]),
            before, "somebody read a watch-list entry and left no trace")

    def test_creating_and_confirming_are_audited_separately(self):
        Audit = self.env["analitix.audit.log"]
        entry = self._entry(created_by=self.officer)
        self.assertTrue(Audit.search([
            ("action", "=", "watchlist_add"), ("res_id", "=", entry.id)]))
        entry.with_user(self.second_officer).action_confirm()
        self.assertTrue(Audit.search([
            ("action", "=", "watchlist_confirm"), ("res_id", "=", entry.id)]))

    def test_recipients_must_be_able_to_open_what_they_are_told_about(self):
        """Warning somebody who cannot see why is how a discreet prompt turns
        into a rumour."""
        with self.assertRaises(ValidationError):
            self.store_one.watchlist_user_ids = [(4, self.shop_manager.id)]


@tagged("post_install", "-at_install")
class TestWatchlistConfigurability(WatchCase):
    """Task 975's central rule, applied to the most sensitive feature.

    Two stores with genuinely different watch-list policies have to coexist,
    and nothing about either may be baked into the code.
    """

    def test_two_stores_hold_different_policies(self):
        self.store_three.write({
            "watchlist_enabled": True,
            "watchlist_threshold": 0.92,
            "watchlist_min_liveness": 0.9,
            "watchlist_review_days": 15,
            "watchlist_expiry_days": 45,
            "watchlist_user_ids": [(6, 0, [self.second_officer.id])],
        })
        self.assertNotEqual(self.store_one.watchlist_threshold,
                            self.store_three.watchlist_threshold)
        self.assertNotEqual(self.store_one.watchlist_user_ids,
                            self.store_three.watchlist_user_ids)

        strict = self.Watch.with_user(self.officer).create({
            "store_id": self.store_three.id,
            "display_label": "Mall entry",
            "reason": "Different store, different policy.",
            "incident_date": fields.Date.context_today(self.env.user),
        })
        self.assertEqual(
            strict.expires_on, fields.Date.add(fields.Date.today(), days=45),
            "the entry took its dates from something other than its own store")

    def test_a_fresh_store_has_no_watch_list_at_all(self):
        """The default has to be the safe one: a shop that never asked for this
        feature must not find it running."""
        fresh = self.Store.create({
            "name": "Fresh", "code": "FR", "company_id": self.company.id,
            "tz": "UTC",
        })
        self.assertFalse(fresh.watchlist_enabled)
        self.assertFalse(fresh.watchlist_user_ids)
        self.assertFalse(fresh.watch_person_ids)
