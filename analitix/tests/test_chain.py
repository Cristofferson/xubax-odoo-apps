# -*- coding: utf-8 -*-
"""Phase 7: chains, regional scope, the console and the elevated decisions.

The weight here is on what a role *cannot* do. A wrong record rule on this
model is not a bug that annoys somebody — it is one customer's branch data
inside another's screen, or a district manager reading a chain they were never
given. So the negative cases outnumber the positive ones, deliberately.
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from .common import AnalitixCase


class ChainCase(AnalitixCase):
    """A two-region chain, plus the four roles that read it differently."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Brand = cls.env["analitix.brand"]
        cls.Region = cls.env["analitix.region"]
        cls.Daily = cls.env["analitix.store.daily"]
        cls.Console = cls.env["analitix.chain.report"]

        cls.brand = cls.Brand.create({
            "name": "Joyerías del Bajío", "code": "JB",
            "company_id": cls.company.id,
        })
        cls.north = cls.Region.create({
            "name": "North", "code": "N", "brand_id": cls.brand.id})
        cls.south = cls.Region.create({
            "name": "South", "code": "S", "brand_id": cls.brand.id})

        # The base fixture's two stores join the chain, one region each.
        cls.store_one.write({"region_id": cls.north.id, "brand_id": cls.brand.id})
        cls.store_three.write({"region_id": cls.south.id, "brand_id": cls.brand.id})

        def make_user(name, login, groups, **extra):
            vals = {
                "name": name, "login": login,
                "group_ids": [(4, cls.env.ref("base.group_user").id)]
                             + [(4, cls.env.ref(g).id) for g in groups],
            }
            vals.update(extra)
            return cls.env["res.users"].with_context(
                no_reset_password=True).create(vals)

        cls.floor = make_user(
            "Floor", "analitix_chain_floor@example.com", ["analitix.group_user"],
            analitix_store_ids=[(6, 0, cls.store_one.ids)])
        cls.store_manager = make_user(
            "Store manager", "analitix_chain_sm@example.com",
            ["analitix.group_manager"],
            analitix_store_ids=[(6, 0, cls.store_one.ids)])
        cls.regional = make_user(
            "Regional", "analitix_chain_rm@example.com",
            ["analitix.group_regional"],
            analitix_region_ids=[(6, 0, cls.north.ids)])
        cls.corporate = make_user(
            "Head office", "analitix_chain_hq@example.com",
            ["analitix.group_corporate"])


@tagged("post_install", "-at_install")
class TestChainStructure(ChainCase):

    def test_a_store_can_belong_to_a_region_and_a_chain(self):
        self.assertEqual(self.store_one.region_id, self.north)
        self.assertEqual(self.store_one.brand_id, self.brand)
        self.assertEqual(self.brand.store_count, 2)
        self.assertEqual(self.brand.region_count, 2)

    def test_a_store_cannot_fly_two_flags(self):
        """A region of chain A while assigned to chain B would break every
        rollup: the region's report would include it and the chain's would not,
        and nobody could tell which figure was wrong."""
        other = self.Brand.create({"name": "Other", "company_id": self.company.id})
        with self.assertRaises(ValidationError):
            self.store_one.brand_id = other.id

    def test_a_single_store_customer_needs_none_of_this(self):
        """Phase 7 must cost the shop that will never use it exactly nothing."""
        plain = self.Store.create({
            "name": "Corner shop", "code": "CS",
            "company_id": self.company.id, "tz": "UTC",
        })
        self.assertFalse(plain.region_id)
        self.assertFalse(plain.brand_id)
        # And the scope helpers still answer "just me".
        self.assertEqual(plain._reid_scope_store_ids(), plain.ids)
        self.assertEqual(plain._watchlist_scope_store_ids(), plain.ids)


@tagged("post_install", "-at_install")
class TestHierarchicalScope(ChainCase):
    """Who sees which stores, resolved from stores *and* regions."""

    def test_a_region_grants_every_store_in_it(self):
        self.assertIn(self.store_one, self.regional.analitix_scope_store_ids)
        self.assertTrue(self.regional.analitix_scoped)

    def test_a_region_grants_stores_that_did_not_exist_yet(self):
        """The reason a region beats a hand-written list of stores: the list
        goes stale the first time the chain grows and nobody updates it."""
        opened_later = self.Store.create({
            "name": "New branch", "code": "NB", "company_id": self.company.id,
            "tz": "UTC", "region_id": self.north.id, "brand_id": self.brand.id,
        })
        self.regional.invalidate_recordset()
        self.assertIn(opened_later, self.regional.analitix_scope_store_ids)

    def test_a_regional_cannot_see_another_region(self):
        visible = self.Store.with_user(self.regional).search([])
        self.assertIn(self.store_one, visible)
        self.assertNotIn(self.store_three, visible,
                         "a regional manager reached a region they were not given")

    def test_a_store_manager_cannot_see_the_rest_of_the_chain(self):
        visible = self.Store.with_user(self.store_manager).search([])
        self.assertEqual(visible, self.store_one)

    def test_an_unscoped_corporate_user_sees_the_whole_chain(self):
        visible = self.Store.with_user(self.corporate).search([])
        self.assertIn(self.store_one, visible)
        self.assertIn(self.store_three, visible)

    def test_an_empty_region_still_restricts(self):
        """A user given a region that holds no stores yet is a *restricted*
        user. Falling through to 'sees everything' because the resolved list
        happened to be empty would be the worst possible failure mode."""
        empty = self.Region.create({
            "name": "Planned", "code": "P", "brand_id": self.brand.id})
        self.regional.write({"analitix_region_ids": [(6, 0, empty.ids)]})
        self.regional.invalidate_recordset()
        self.assertTrue(self.regional.analitix_scoped)
        self.assertFalse(self.Store.with_user(self.regional).search([]))

    def test_stores_and_regions_add_up_rather_than_fight(self):
        self.regional.write({
            "analitix_store_ids": [(6, 0, self.store_three.ids)],
            "analitix_region_ids": [(6, 0, self.north.ids)],
        })
        self.regional.invalidate_recordset()
        visible = self.Store.with_user(self.regional).search([])
        self.assertIn(self.store_one, visible, "the region was dropped")
        self.assertIn(self.store_three, visible, "the direct store was dropped")

    def test_the_scope_follows_a_store_moving_region(self):
        """A cached scope that goes stale is a user still reading a branch they
        were moved off — which is the whole reason it is not stored."""
        self.assertIn(self.store_one, self.regional.analitix_scope_store_ids)
        self.store_one.region_id = self.south.id
        self.regional.invalidate_recordset()
        self.assertNotIn(self.store_one, self.regional.analitix_scope_store_ids)


@tagged("post_install", "-at_install")
class TestElevatedScopeControl(ChainCase):
    """The two decisions that only head office may take."""

    def test_a_store_manager_cannot_widen_recognition(self):
        with self.assertRaises(UserError):
            self.brand.with_user(self.store_manager).reid_scope = "chain"

    def test_a_regional_manager_cannot_widen_recognition_either(self):
        with self.assertRaises(UserError):
            self.brand.with_user(self.regional).reid_scope = "chain"

    def test_corporate_can_and_it_is_recorded(self):
        Audit = self.env["analitix.audit.log"]
        before = Audit.search_count([("action", "=", "elevated")])
        self.brand.with_user(self.corporate).reid_scope = "chain"
        self.brand.invalidate_recordset()
        self.assertEqual(self.brand.reid_scope, "chain")
        self.assertEqual(self.brand.scope_changed_by_id, self.corporate)
        self.assertGreater(
            Audit.search_count([("action", "=", "elevated")]), before,
            "a chain-wide recognition change left no audit entry")

    def test_recognition_is_isolated_until_somebody_says_otherwise(self):
        self.assertEqual(self.brand.reid_scope, "store")
        self.assertEqual(self.store_one._reid_scope_store_ids(), self.store_one.ids)

    def test_widening_recognition_reaches_the_matching_code(self):
        """The setting has to change behaviour, not just a column."""
        self.brand.with_user(self.corporate).reid_scope = "chain"
        scope = self.store_one._reid_scope_store_ids()
        self.assertIn(self.store_one.id, scope)
        self.assertIn(self.store_three.id, scope)

    def test_matching_is_never_unbounded(self):
        """Even chain-wide, one arriving face is compared against one chain —
        not against every signature in the database."""
        outsider = self.Store.create({
            "name": "Someone else's shop", "code": "XX",
            "company_id": self.company.id, "tz": "UTC",
        })
        self.brand.with_user(self.corporate).reid_scope = "chain"
        self.assertNotIn(outsider.id, self.store_one._reid_scope_store_ids())

    def test_the_watch_list_is_shared_across_a_chain_by_default(self):
        """The opposite default from recognition, and for the opposite reason:
        an incident at one branch is worth the others knowing."""
        self.assertEqual(self.brand.watchlist_scope, "chain")
        scope = self.store_one._watchlist_scope_store_ids()
        self.assertIn(self.store_three.id, scope)

    def test_narrowing_the_watch_list_is_just_as_elevated(self):
        with self.assertRaises(UserError):
            self.brand.with_user(self.store_manager).watchlist_scope = "store"
        self.brand.with_user(self.corporate).watchlist_scope = "store"
        self.assertEqual(
            self.store_one._watchlist_scope_store_ids(), self.store_one.ids)


@tagged("post_install", "-at_install")
class TestDailyRollup(ChainCase):

    def setUp(self):
        super().setUp()
        self.today = fields.Date.context_today(self.env.user)
        self.yesterday = fields.Date.subtract(self.today, days=1)
        # Traffic at a time of day both stores are certainly open, expressed in
        # the store's own timezone so the rollup and the fixture agree.
        start, _end = self.store_one._day_bounds(self.yesterday)
        self.slot = start + timedelta(hours=13)

    def test_a_day_is_summarised_per_store(self):
        for _ in range(12):
            self.make_event(self.device_one, "in", when=self.slot)
        self.Daily.roll_up(self.store_one, self.yesterday)

        row = self.Daily.search([
            ("store_id", "=", self.store_one.id), ("day", "=", self.yesterday)])
        self.assertEqual(len(row), 1)
        self.assertEqual(row.visitors, 12)

    def test_rolling_up_twice_does_not_double_the_figures(self):
        """A cron that fires twice after a restart has to be harmless."""
        for _ in range(7):
            self.make_event(self.device_one, "in", when=self.slot)
        self.Daily.roll_up(self.store_one, self.yesterday)
        self.Daily.roll_up(self.store_one, self.yesterday)

        rows = self.Daily.search([
            ("store_id", "=", self.store_one.id), ("day", "=", self.yesterday)])
        self.assertEqual(len(rows), 1, "the rollup created a second row")
        self.assertEqual(rows.visitors, 7)

    def test_the_ratios_are_computed_not_copied(self):
        for _ in range(20):
            self.make_event(self.device_one, "in", when=self.slot)
        self.Daily.roll_up(self.store_one, self.yesterday)
        row = self.Daily.search([
            ("store_id", "=", self.store_one.id), ("day", "=", self.yesterday)])
        row.write({"tickets": 5, "units": 15, "revenue": 1000.0})
        self.assertAlmostEqual(row.conversion_rate, 25.0, places=2)
        self.assertAlmostEqual(row.atv, 200.0, places=2)
        self.assertAlmostEqual(row.upt, 3.0, places=2)

    def test_a_day_is_the_stores_day_not_the_servers(self):
        """A chain across two timezones reporting on UTC days would compare two
        different things and call it a comparison."""
        self.store_one.tz = "Pacific/Auckland"
        auckland, _end = self.store_one._day_bounds(self.yesterday)
        self.store_one.tz = "America/Mexico_City"
        mexico, _end2 = self.store_one._day_bounds(self.yesterday)
        self.assertNotEqual(auckland, mexico)

    def test_rescue_rate_separates_traffic_from_floor(self):
        self.Daily.roll_up(self.store_one, self.yesterday)
        row = self.Daily.search([
            ("store_id", "=", self.store_one.id), ("day", "=", self.yesterday)])
        row.write({"lost_detected": 10, "lost_rescued": 4})
        self.assertAlmostEqual(row.rescue_rate, 40.0, places=2)


@tagged("post_install", "-at_install")
class TestChainConsole(ChainCase):
    """The screen the chain is sold on."""

    def setUp(self):
        super().setUp()
        self.day = fields.Date.subtract(
            fields.Date.context_today(self.env.user), days=1)
        # Two branches of the same region, same day, deliberately unequal: the
        # console exists to make exactly this difference visible.
        self.store_two = self.Store.create({
            "name": "Second northern branch", "code": "N2",
            "company_id": self.company.id, "tz": "UTC",
            "region_id": self.north.id, "brand_id": self.brand.id,
            "area_sqm": 100.0,
        })
        self.Daily.create([
            {"store_id": self.store_one.id, "day": self.day,
             "visitors": 100, "tickets": 30, "units": 45, "revenue": 6000.0,
             "lost_detected": 10, "lost_rescued": 8},
            {"store_id": self.store_two.id, "day": self.day,
             "visitors": 100, "tickets": 10, "units": 12, "revenue": 2000.0,
             "lost_detected": 10, "lost_rescued": 1},
        ])
        self.env.flush_all()

    def _row(self, store):
        return self.Console.search([
            ("store_id", "=", store.id), ("day", "=", self.day)], limit=1)

    def test_the_console_measures_every_branch_the_same_way(self):
        good, bad = self._row(self.store_one), self._row(self.store_two)
        self.assertAlmostEqual(good.conversion_rate, 30.0, places=1)
        self.assertAlmostEqual(bad.conversion_rate, 10.0, places=1)
        self.assertAlmostEqual(good.atv, 200.0, places=1)

    def test_the_difference_against_the_region_is_the_actionable_number(self):
        """Same footfall, a third of the sales — with the week, the weather and
        the season removed, because they move every branch together."""
        good, bad = self._row(self.store_one), self._row(self.store_two)
        self.assertAlmostEqual(good.conversion_vs_region, 10.0, places=1)
        self.assertAlmostEqual(bad.conversion_vs_region, -10.0, places=1)

    def test_rescue_rate_shows_which_problem_it_is(self):
        self.assertAlmostEqual(self._row(self.store_one).rescue_rate, 80.0, places=1)
        self.assertAlmostEqual(self._row(self.store_two).rescue_rate, 10.0, places=1)

    def test_density_is_how_a_kiosk_is_compared_to_a_flagship(self):
        self.assertAlmostEqual(
            self._row(self.store_two).revenue_per_sqm, 20.0, places=1)

    def test_a_store_with_no_region_is_not_compared_to_one(self):
        loner = self.Store.create({
            "name": "Independent", "code": "IND", "company_id": self.company.id,
            "tz": "UTC"})
        self.Daily.create({
            "store_id": loner.id, "day": self.day, "visitors": 50, "tickets": 5})
        self.env.flush_all()
        self.assertEqual(self._row(loner).conversion_vs_region, 0.0)

    def test_a_regional_sees_only_their_own_region_in_the_console(self):
        rows = self.Console.with_user(self.regional).search([])
        self.assertTrue(rows)
        self.assertNotIn(self.store_three, rows.mapped("store_id"),
                         "the console leaked a region the user was not given")

    def test_a_floor_salesperson_cannot_open_the_console_at_all(self):
        with self.assertRaises(AccessError):
            self.Console.with_user(self.floor).search([])


@tagged("post_install", "-at_install")
class TestEventPruning(ChainCase):
    """Pruning is the one irreversible operation in this addon."""

    RETENTION_DAYS = 90

    def setUp(self):
        super().setUp()
        self.param = self.env["ir.config_parameter"].sudo()
        today = fields.Date.context_today(self.env.user)
        self.old_day = fields.Date.subtract(today, days=400)
        start, _end = self.store_one._day_bounds(self.old_day)
        self.old_event = self.make_event(
            self.device_one, "in", when=start + timedelta(hours=12))
        # The oldest day pruning may reach, given the policy set below.
        self.cutoff_day = fields.Date.subtract(today, days=self.RETENTION_DAYS)

    def _summarise_up_to_cutoff(self):
        """Roll up the old day AND a later one inside the retention window.

        In production the nightly job leaves an unbroken run of rollups, and
        pruning walks up to the most recent one still older than the policy. A
        test that summarised only the single day it wanted deleted would be
        asking the guard to prune into a gap it has never summarised — which it
        refuses to do, correctly.
        """
        self.Daily.roll_up(self.store_one, self.old_day)
        self.Daily.roll_up(
            self.store_one, fields.Date.subtract(self.cutoff_day, days=1))

    def test_nothing_is_pruned_unless_a_policy_asks_for_it(self):
        """Turning deletion on by default at upgrade time would destroy data a
        customer never agreed to lose."""
        self.param.set_param("analitix.event_retention_days", "0")
        self.Daily.prune_events()
        self.assertTrue(self.old_event.exists())

    def test_nothing_is_pruned_ahead_of_the_rollup(self):
        """The guard that makes retention safe to switch on: without a summary,
        deleting the events destroys figures nobody ever computed."""
        self.param.set_param(
            "analitix.event_retention_days", str(self.RETENTION_DAYS))
        self.Daily.search([("store_id", "=", self.store_one.id)]).unlink()
        self.Daily.prune_events()
        self.assertTrue(
            self.old_event.exists(),
            "events were deleted for a day that had never been summarised")

    def test_a_summarised_day_can_be_pruned_and_the_figures_survive(self):
        self._summarise_up_to_cutoff()
        row = self.Daily.search([
            ("store_id", "=", self.store_one.id), ("day", "=", self.old_day)])
        self.assertEqual(row.visitors, 1)

        self.param.set_param(
            "analitix.event_retention_days", str(self.RETENTION_DAYS))
        self.Daily.prune_events()

        self.assertFalse(self.old_event.exists(), "the old event was not pruned")
        row.invalidate_recordset()
        self.assertEqual(row.visitors, 1,
                         "pruning destroyed a figure the report still shows")

    def test_recent_traffic_is_never_touched(self):
        self._summarise_up_to_cutoff()
        fresh = self.make_event(self.device_one, "in")
        self.param.set_param(
            "analitix.event_retention_days", str(self.RETENTION_DAYS))
        self.Daily.prune_events()
        self.assertTrue(fresh.exists(), "today's traffic was pruned")

    def test_the_legacy_cron_still_works(self):
        """Existing installations have a scheduled action pointing at the event
        model. It must keep working, and must go through the same guards."""
        self.param.set_param(
            "analitix.event_retention_days", str(self.RETENTION_DAYS))
        self._summarise_up_to_cutoff()
        self.env["analitix.event"]._cron_apply_retention()
        self.assertFalse(self.old_event.exists())
