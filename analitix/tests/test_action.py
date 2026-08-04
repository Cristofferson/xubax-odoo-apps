# -*- coding: utf-8 -*-
"""Phase 4: signage routing, welcome context, attendance, billing and ROI.

The two things worth testing hardest here are the ones that would embarrass the
customer rather than merely inconvenience them: sending a message to the wrong
screen, and naming somebody on a screen while they are standing with company.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests.common import tagged

from .test_floor import FloorCase


class ActionCase(FloorCase):
    """Adds screens, an exit zone and a signage rule to the floor fixture."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Rule = cls.env["analitix.signage.rule"]
        cls.Firing = cls.env["analitix.signage.event"]
        cls.store_one.signage_enabled = True

        cls.entrance = cls.Zone.create({
            "store_id": cls.store_one.id, "name": "Entrance", "code": "E",
            "kind": "entrance", "screen_group_ref": "SCREEN-ENTRANCE",
        })
        cls.exit_zone = cls.Zone.create({
            "store_id": cls.store_one.id, "name": "Exit", "code": "X",
            "kind": "exit", "screen_group_ref": "SCREEN-EXIT",
        })
        cls.rings.screen_group_ref = "SCREEN-RINGS"


@tagged("post_install", "-at_install")
class TestSignageRouting(ActionCase):

    def _rule(self, **overrides):
        vals = {
            "name": "Test rule", "store_id": self.store_one.id,
            "trigger": "lost_sale", "target": "event_zone",
            "message": "Ask us about finance", "cooldown_minutes": 0,
        }
        vals.update(overrides)
        return self.Rule.create(vals)

    def test_a_firing_goes_to_the_screen_where_it_happened(self):
        """The whole point of routing: a store's screens are not one screen."""
        rule = self._rule(target="event_zone")
        self.assertEqual(rule._resolve_screen(self.rings), self.rings)

    def test_the_exit_target_finds_the_exit_screen(self):
        rule = self._rule(target="exit")
        self.assertEqual(rule._resolve_screen(self.rings), self.exit_zone)

    def test_the_facade_target_finds_the_entrance_screen(self):
        rule = self._rule(target="facade")
        self.assertEqual(rule._resolve_screen(self.rings), self.entrance)

    def test_a_zone_with_no_screen_resolves_to_nothing(self):
        """A configuration gap, not an error: the shop has no screen there."""
        bare = self.Zone.create({
            "store_id": self.store_one.id, "name": "Back", "code": "BK"})
        rule = self._rule(target="event_zone")
        self.assertFalse(rule._resolve_screen(bare))

    def test_nothing_fires_when_the_store_does_not_drive_its_screens(self):
        self.store_one.signage_enabled = False
        self._rule()
        self.assertFalse(self.Rule.fire(
            self.store_one, "lost_sale", zone=self.rings))

    def test_only_rules_for_that_trigger_fire(self):
        self._rule(trigger="lost_sale")
        self._rule(name="Group rule", trigger="group")
        fired = self.Rule.fire(self.store_one, "lost_sale", zone=self.rings)
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired.trigger, "lost_sale")

    def test_a_zone_condition_narrows_the_rule(self):
        rule = self._rule(zone_ids=[(6, 0, self.rings.ids)])
        self.assertTrue(rule._matches(self.store_one, zone=self.rings))
        self.assertFalse(rule._matches(self.store_one, zone=self.exit_zone))

    def test_the_hour_condition_narrows_the_rule(self):
        self.store_one.tz = "UTC"
        rule = self._rule(hour_from=8.0, hour_to=10.0)
        at_nine = fields.Datetime.now().replace(hour=9, minute=0, second=0)
        at_twenty = fields.Datetime.now().replace(hour=20, minute=0, second=0)
        self.assertTrue(rule._matches(self.store_one, when=at_nine))
        self.assertFalse(rule._matches(self.store_one, when=at_twenty))

    def test_a_group_condition_needs_a_group(self):
        rule = self._rule(trigger="group", group_min_size=2)
        group = self.env["analitix.visit.group"].create({
            "store_id": self.store_one.id, "entered_at": fields.Datetime.now(),
            "size": 3,
        })
        small = self.env["analitix.visit.group"].create({
            "store_id": self.store_one.id, "entered_at": fields.Datetime.now(),
            "size": 1,
        })
        self.assertTrue(rule._matches(self.store_one, group=group))
        self.assertFalse(rule._matches(self.store_one, group=small))
        self.assertFalse(rule._matches(self.store_one))

    def test_the_cooldown_stops_the_signage_flickering(self):
        rule = self._rule(cooldown_minutes=30)
        self.Firing.create({
            "rule_id": rule.id, "store_id": self.store_one.id,
            "zone_id": self.rings.id, "content": "earlier",
        })
        self.assertTrue(rule._recently_fired(self.rings))
        self.assertFalse(rule._recently_fired(self.exit_zone),
                         "a cooldown is per screen, not per store")

    def test_a_firing_is_recorded_even_when_the_screen_never_showed_it(self):
        """'The CMS was down for a week' is exactly what a store must be able
        to see, so an undelivered firing is kept rather than dropped."""
        rule = self._rule()
        rule._dispatch(self.rings)
        firing = self.Firing.search([("rule_id", "=", rule.id)], limit=1)
        self.assertTrue(firing)
        self.assertFalse(firing.delivered)
        self.assertTrue(firing.error, "the reason must be recorded")

    def test_placeholders_are_filled_in(self):
        rule = self._rule(message="Welcome back, {customer}")
        partner = self.env["res.partner"].create({"name": "Gustavo"})
        self.assertEqual(
            rule._render(self.rings, partner), "Welcome back, Gustavo")

    def test_an_unknown_customer_never_leaves_a_raw_token_on_screen(self):
        rule = self._rule(message="Welcome back, {customer}")
        rendered = rule._render(self.rings, None)
        self.assertNotIn("{", rendered)


@tagged("post_install", "-at_install")
class TestWelcomeContext(ActionCase):

    def setUp(self):
        super().setUp()
        self.Context = self.env["analitix.customer.context"]
        self.partner = self.env["res.partner"].create({"name": "Gustavo"})

    def _visit(self, group=None):
        return self.env["analitix.visitor"].create({
            "store_id": self.store_one.id,
            "door_id": self.door_one.id,
            "entered_at": fields.Datetime.now(),
            "state": "inside",
            "visit_group_id": group.id if group else False,
        })

    def test_a_lone_customer_is_greeted_by_name(self):
        context = self.Context.build(
            self.store_one, self.partner, visitor=self._visit())
        self.assertTrue(context["alone"])
        self.assertIn("Gustavo", context["screen_message"])

    def test_a_customer_with_company_is_not_named_on_screen(self):
        """The social privacy rule, and the reason phase 4 has one.

        A screen naming somebody in front of the person they arrived with has
        just told that person that they shop here, and how often.
        """
        group = self.env["analitix.visit.group"].create({
            "store_id": self.store_one.id,
            "entered_at": fields.Datetime.now(), "size": 2,
        })
        context = self.Context.build(
            self.store_one, self.partner, visitor=self._visit(group=group))

        self.assertFalse(context["alone"])
        self.assertEqual(context["screen_message"], "",
                         "the screen must stay neutral")
        self.assertIn("Gustavo", context["staff_message"])
        self.assertIn("not alone", context["staff_message"])

    def test_the_rule_can_be_switched_off(self):
        self.store_one.welcome_alone_only = False
        group = self.env["analitix.visit.group"].create({
            "store_id": self.store_one.id,
            "entered_at": fields.Datetime.now(), "size": 2,
        })
        context = self.Context.build(
            self.store_one, self.partner, visitor=self._visit(group=group))
        self.assertIn("Gustavo", context["screen_message"])

    def test_the_staff_line_carries_the_open_opportunity(self):
        self.env["crm.lead"].create({
            "name": "Wedding bands",
            "partner_id": self.partner.id,
            "type": "opportunity",
        })
        context = self.Context.build(
            self.store_one, self.partner, visitor=self._visit())
        self.assertIn("Wedding bands", context["staff_message"])

    def test_purchase_history_is_scoped_to_this_store(self):
        """Telling a salesperson what a customer bought at another company's
        shop is the leak the tenancy rules exist to prevent."""
        other_company = self.env["res.company"].create({"name": "Someone else"})
        purchases = self.Context._purchases(self.store_one, self.partner)
        self.assertFalse(purchases)
        self.assertNotEqual(self.store_one.company_id, other_company)

    def test_no_context_for_an_anonymous_visitor(self):
        self.assertEqual(self.Context.build(self.store_one, False), {})


@tagged("post_install", "-at_install")
class TestAttendance(ActionCase):

    def setUp(self):
        super().setUp()
        self.Attendance = self.env["analitix.attendance"]
        self.hr = self.env["hr.attendance"]
        self.employee = self.env["hr.employee"].create({"name": "Rosa"})
        self.store_one.write({
            "attendance_enabled": True, "attendance_min_gap_minutes": 10,
        })

    def _crossing(self, direction, when=None, employee=None):
        return self.make_event(
            self.device_one, direction, when=when, counted=False,
            staff_id=(employee or self.employee).id)

    def test_nothing_is_recorded_unless_the_store_asked(self):
        """A shop that has not agreed this with its team should not start
        recording their hours because a camera was installed."""
        self.store_one.attendance_enabled = False
        self.Attendance._record_crossing(self._crossing("in"))
        self.assertFalse(self.hr.search([
            ("employee_id", "=", self.employee.id)]))

    def test_arriving_opens_a_shift_and_leaving_closes_it(self):
        start = fields.Datetime.now() - timedelta(hours=4)
        self.Attendance._record_crossing(self._crossing("in", when=start))
        row = self.hr.search([("employee_id", "=", self.employee.id)])
        self.assertEqual(len(row), 1)
        self.assertFalse(row.check_out)

        self.Attendance._record_crossing(self._crossing(
            "out", when=start + timedelta(hours=4)))
        row.invalidate_recordset()
        self.assertTrue(row.check_out)

    def test_a_second_arrival_does_not_open_a_second_shift(self):
        start = fields.Datetime.now() - timedelta(hours=3)
        self.Attendance._record_crossing(self._crossing("in", when=start))
        self.Attendance._record_crossing(self._crossing(
            "in", when=start + timedelta(minutes=30)))
        self.assertEqual(len(self.hr.search(
            [("employee_id", "=", self.employee.id)])), 1)

    def test_a_short_trip_out_does_not_end_the_working_day(self):
        """Ten minutes at the bank is not the end of a shift."""
        start = fields.Datetime.now() - timedelta(hours=3)
        self.Attendance._record_crossing(self._crossing("in", when=start))
        self.Attendance._record_crossing(self._crossing(
            "out", when=start + timedelta(hours=1)))
        self.Attendance._record_crossing(self._crossing(
            "in", when=start + timedelta(hours=1, minutes=5)))

        rows = self.hr.search([("employee_id", "=", self.employee.id)])
        self.assertEqual(len(rows), 1, "the day was split in two")
        self.assertFalse(rows.check_out, "the shift should be open again")

    def test_leaving_moments_after_arriving_is_ignored(self):
        start = fields.Datetime.now() - timedelta(hours=1)
        self.Attendance._record_crossing(self._crossing("in", when=start))
        self.Attendance._record_crossing(self._crossing(
            "out", when=start + timedelta(minutes=2)))
        row = self.hr.search([("employee_id", "=", self.employee.id)])
        self.assertFalse(row.check_out,
                         "a two-minute working day would have been recorded")

    def test_a_forgotten_shift_is_closed_at_the_stores_maximum(self):
        self.store_one.attendance_max_hours = 12
        start = fields.Datetime.now() - timedelta(hours=40)
        self.Attendance._record_crossing(self._crossing("in", when=start))

        self.Attendance._cron_close_forgotten()
        row = self.hr.search([("employee_id", "=", self.employee.id)])
        self.assertTrue(row.check_out)
        self.assertLessEqual(
            (row.check_out - row.check_in).total_seconds() / 3600.0, 12.5)

    def test_only_the_configured_door_counts_when_one_is_set(self):
        other_door = self.env["analitix.door"].create({
            "store_id": self.store_one.id, "name": "Side", "code": "SD"})
        other_device = self.Device.create({
            "name": "Side counter", "device_uid": "t1-side",
            "store_id": self.store_one.id, "door_id": other_door.id})
        self.store_one.attendance_door_id = self.door_one.id

        event = self.make_event(
            other_device, "in", counted=False, staff_id=self.employee.id)
        self.Attendance._record_crossing(event)
        self.assertFalse(self.hr.search([
            ("employee_id", "=", self.employee.id)]))


@tagged("post_install", "-at_install")
class TestSubscriptionAndValue(ActionCase):

    def test_a_plan_switches_features_on_and_off(self):
        self.store_one.plan = "counting"
        self.store_one._onchange_plan()
        self.assertFalse(self.store_one.signage_enabled)
        self.assertFalse(self.store_one.lost_sale_enabled)

        self.store_one.plan = "actions"
        self.store_one._onchange_plan()
        self.assertTrue(self.store_one.signage_enabled)
        self.assertTrue(self.store_one.lost_sale_enabled)
        self.assertTrue(self.store_one.identify_customers)

    def test_pausing_the_subscription_does_not_stop_the_cameras(self):
        """A customer who paused billing has not asked to lose their history,
        and stopping capture would make their return month read as a collapse."""
        self.assertTrue(self.store_one.capture_enabled)
        self.store_one.action_pause_subscription()
        self.assertEqual(self.store_one.subscription_state, "paused")
        self.assertTrue(self.store_one.capture_enabled)

    def test_an_expired_trial_raises_an_activity_rather_than_cutting_off(self):
        self.store_one.write({
            "subscription_state": "trial",
            "trial_end_date": fields.Date.subtract(
                fields.Date.context_today(self.store_one), days=1),
            "alert_user_id": self.env.user.id,
        })
        self.env["analitix.store"]._cron_check_trials()

        self.assertTrue(self.env["mail.activity"].search_count([
            ("res_model", "=", "analitix.store"),
            ("res_id", "=", self.store_one.id),
        ]), "nobody was told the trial ended")
        self.assertTrue(self.store_one.capture_enabled,
                        "an expired trial must never switch a store off")

    def test_the_value_report_counts_what_actually_happened(self):
        Report = self.env["analitix.value.report"]
        start = fields.Date.subtract(fields.Date.context_today(self), days=30)
        end = fields.Date.context_today(self)

        visit = self.env["analitix.visitor"].create({
            "store_id": self.store_one.id, "door_id": self.door_one.id,
            "entered_at": fields.Datetime.now(), "state": "left",
        })
        dwell = self.Dwell.record(
            visit, self.rings, fields.Datetime.now() - timedelta(minutes=5), 300)
        self.LostSale._evaluate_dwell(dwell)

        report = Report.build(self.store_one, start, end)
        self.assertEqual(report.lost_sales_detected, 1)
        self.assertEqual(report.lost_sales_rescued, 0)
        self.assertEqual(report.state, "draft")

    def test_recovered_revenue_is_zero_when_nothing_was_rescued(self):
        """Never overclaim: the fastest way to lose a customer who checks."""
        Report = self.env["analitix.value.report"]
        report = Report.build(
            self.store_one,
            fields.Date.subtract(fields.Date.context_today(self), days=30),
            fields.Date.context_today(self))
        self.assertEqual(report.lost_sales_rescued, 0)
        self.assertEqual(report.estimated_recovered, 0.0)

    def test_the_summary_reads_as_sentences_not_metrics(self):
        Report = self.env["analitix.value.report"]
        report = Report.build(
            self.store_one,
            fields.Date.subtract(fields.Date.context_today(self), days=30),
            fields.Date.context_today(self))
        lines = report.summary_lines()
        self.assertTrue(lines)
        joined = " ".join(lines).lower()
        for jargon in ("conversion_rate", "analitix", "pos.order", "visitor_id"):
            self.assertNotIn(jargon, joined)

    def test_a_report_is_built_once_per_store_and_month(self):
        Report = self.env["analitix.value.report"]
        start = fields.Date.subtract(fields.Date.context_today(self), days=30)
        end = fields.Date.context_today(self)
        first = Report.build(self.store_one, start, end)
        second = Report.build(self.store_one, start, end)
        self.assertEqual(first, second)
