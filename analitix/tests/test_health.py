# -*- coding: utf-8 -*-
"""Device health, alerting and the job queue (task 982)."""
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import tagged

from .common import AnalitixCase


@tagged("post_install", "-at_install")
class TestDeviceHealth(AnalitixCase):

    def _silence(self, device, minutes):
        """Pretend the device last spoke ``minutes`` ago."""
        device.sudo().write({
            "last_heartbeat": fields.Datetime.now() - timedelta(minutes=minutes),
        })

    def test_a_new_device_starts_as_never_seen(self):
        self.assertEqual(self.device_one.status, "never_seen")

    def test_a_heartbeat_brings_it_online(self):
        self.device_one._mark_seen(agent_version="9.9.9")
        self.assertEqual(self.device_one.status, "online")
        self.assertEqual(self.device_one.agent_version, "9.9.9")

    def test_silence_past_the_threshold_marks_it_offline(self):
        self.store_one.write({
            "degraded_threshold_min": 2, "offline_threshold_min": 5})
        self.device_one._mark_seen()
        self._silence(self.device_one, 10)

        self.Device._cron_check_health()
        self.assertEqual(self.device_one.status, "offline")
        self.assertTrue(self.device_one.offline_since)

    def test_the_grace_band_reports_late_not_dead(self):
        self.store_one.write({
            "degraded_threshold_min": 2, "offline_threshold_min": 30})
        self.device_one._mark_seen()
        self._silence(self.device_one, 5)

        self.Device._cron_check_health()
        self.assertEqual(self.device_one.status, "degraded")

    def test_the_threshold_really_is_per_store(self):
        """Same silence, different verdicts — a flaky site can be given slack."""
        self.store_one.write({
            "degraded_threshold_min": 1, "offline_threshold_min": 3})
        self.store_three.write({
            "degraded_threshold_min": 30, "offline_threshold_min": 60})
        self.device_one._mark_seen()
        self.devices_three[0]._mark_seen()
        self._silence(self.device_one, 10)
        self._silence(self.devices_three[0], 10)

        self.Device._cron_check_health()
        self.assertEqual(self.device_one.status, "offline")
        self.assertEqual(self.devices_three[0].status, "online")

    def test_recovery_clears_the_offline_state(self):
        self.store_one.offline_threshold_min = 5
        self.device_one._mark_seen()
        self._silence(self.device_one, 10)
        self.Device._cron_check_health()
        self.assertEqual(self.device_one.status, "offline")

        self.device_one._mark_seen()
        self.assertEqual(self.device_one.status, "online")
        self.assertFalse(self.device_one.offline_since)

    def test_a_critical_device_going_down_raises_an_activity(self):
        self.store_one.write({
            "offline_threshold_min": 5, "alert_user_id": self.env.user.id})
        self.device_one.critical = True
        self.device_one._mark_seen()
        self._silence(self.device_one, 20)

        self.Device._cron_check_health()
        activity = self.env["mail.activity"].search([
            ("res_model", "=", "analitix.device"),
            ("res_id", "=", self.device_one.id),
        ])
        self.assertTrue(activity, "nobody was told a critical camera died")

    def test_a_non_critical_device_does_not_page_anyone(self):
        self.store_one.offline_threshold_min = 5
        self.device_one.critical = False
        self.device_one._mark_seen()
        self._silence(self.device_one, 20)

        self.Device._cron_check_health()
        self.assertEqual(self.device_one.status, "offline")
        self.assertFalse(self.env["mail.activity"].search_count([
            ("res_model", "=", "analitix.device"),
            ("res_id", "=", self.device_one.id)]))

    def test_a_paused_store_does_not_raise_false_alarms(self):
        """Silence during a deliberate pause is expected, not a fault."""
        self.store_one.offline_threshold_min = 5
        self.device_one._mark_seen()
        self._silence(self.device_one, 60)
        self.store_one.action_pause_capture()

        self.Device._cron_check_health()
        self.assertEqual(self.device_one.status, "disabled")
        self.assertFalse(self.env["mail.activity"].search_count([
            ("res_model", "=", "analitix.device"),
            ("res_id", "=", self.device_one.id)]))

    def test_store_health_rolls_up_from_its_devices(self):
        self.store_three.offline_threshold_min = 5
        for device in self.devices_three:
            device._mark_seen()
        self.store_three.invalidate_recordset()
        self.assertEqual(self.store_three.health_state, "ok")

        self.devices_three[0].sudo().write({
            "last_heartbeat": fields.Datetime.now() - timedelta(minutes=30)})
        self.Device._cron_check_health()
        self.store_three.invalidate_recordset()
        self.assertEqual(self.store_three.health_state, "down")


@tagged("post_install", "-at_install")
class TestJobQueue(AnalitixCase):

    def setUp(self):
        super().setUp()
        # Start from an empty queue.
        #
        # _cron_run claims the OLDEST 200 pending jobs, which is right for
        # production and wrong for a test that enqueues one job and expects it
        # to run: on a database installed with demo data the demo shop leaves
        # several hundred jobs queued ahead of it, and the test's own job is
        # never reached. These tests are about the queue's mechanics, not about
        # what happens to be in it, so the ambient backlog is cleared rather
        # than worked around with a bigger limit — a limit large enough today
        # is a limit that breaks again when the demo data grows.
        self.env["analitix.job"].sudo().search(
            [("state", "=", "pending")]).write({"state": "done"})

    def test_a_job_runs_and_is_marked_done(self):
        employee = self.env["hr.employee"].create({"name": "Gaby"})
        self.Signature.enrol(self.store_one, employee, self.fake_vector(21))
        crypto = self.env["analitix.crypto"]
        event = self.make_event(
            self.device_one, "in",
            pending_embedding=crypto.encrypt_vector(
                crypto.normalize(self.fake_vector(21))))

        job = self.env["analitix.job"].enqueue(
            "staff_match", {"event_ids": event.ids}, store=self.store_one)
        self.env["analitix.job"]._cron_run()

        self.assertEqual(job.state, "done")
        event.invalidate_recordset()
        self.assertFalse(event.counted, "the matched employee was still counted")
        self.assertEqual(event.staff_id, employee)

    def test_the_embedding_is_wiped_after_matching(self):
        """The event table is a traffic log, not a biometric store."""
        crypto = self.env["analitix.crypto"]
        event = self.make_event(
            self.device_one, "in",
            pending_embedding=crypto.encrypt_vector(self.fake_vector(31)))
        self.env["analitix.job"].enqueue(
            "staff_match", {"event_ids": event.ids}, store=self.store_one)
        self.env["analitix.job"]._cron_run()

        event.invalidate_recordset()
        self.assertFalse(event.pending_embedding)

    def test_an_unknown_job_kind_fails_loudly_instead_of_hanging(self):
        job = self.env["analitix.job"].enqueue("no_such_handler", {})
        self.env["analitix.job"]._cron_run()
        self.assertEqual(job.state, "failed")
        self.assertIn("no_such_handler", job.error)

    def test_a_failing_job_is_retried_with_backoff(self):
        """A handler that blows up is rescheduled, not silently dropped.

        The handler is patched to raise rather than fed a payload that trips a
        database error: a real SQL failure would be logged at ERROR level and
        the test runner counts those as failures, so the test would report a
        problem while proving the recovery works.
        """
        job = self.env["analitix.job"].enqueue(
            "staff_match", {"event_ids": []}, store=self.store_one)
        with patch.object(
                type(self.env["analitix.staff.signature"]), "_run_staff_match",
                side_effect=ValueError("boom")):
            self.env["analitix.job"]._cron_run()

        self.assertEqual(job.state, "pending", "a failure must be retried")
        self.assertEqual(job.attempts, 1)
        self.assertIn("boom", job.error)
        self.assertGreater(job.scheduled_at, fields.Datetime.now(),
                           "the retry must be pushed into the future")

    def test_a_job_stops_being_retried_once_attempts_run_out(self):
        """Otherwise a permanently broken job retries until the end of time."""
        job = self.env["analitix.job"].enqueue(
            "staff_match", {"event_ids": []}, store=self.store_one)
        job.sudo().write({"attempts": job.max_attempts})
        with patch.object(
                type(self.env["analitix.staff.signature"]), "_run_staff_match",
                side_effect=ValueError("boom")):
            job._run_one()
        self.assertEqual(job.state, "failed")

    def test_one_bad_job_does_not_take_the_batch_with_it(self):
        """The savepoint's whole purpose, stated as a test."""
        bad = self.env["analitix.job"].enqueue(
            "staff_match", {"event_ids": []}, store=self.store_one, priority=1)
        good = self.env["analitix.job"].enqueue(
            "staff_match", {"event_ids": []}, store=self.store_one, priority=2)
        original = type(self.env["analitix.staff.signature"])._run_staff_match

        def fail_first(self_model, job):
            if job.id == bad.id:
                raise ValueError("boom")
            return original(self_model, job)

        with patch.object(
                type(self.env["analitix.staff.signature"]), "_run_staff_match",
                fail_first):
            self.env["analitix.job"]._cron_run()

        self.assertEqual(bad.state, "pending")
        self.assertEqual(good.state, "done",
                         "a poisoned job must not roll back its neighbours")

    def test_a_job_enqueued_inside_the_running_transaction_is_picked_up(self):
        """Regression: the queue is claimed with raw SQL, which sees neither the
        ORM's unflushed rows nor a clock later than the transaction's start.

        PostgreSQL's now() is the *transaction start* time, so a job enqueued
        after the transaction began sits in that transaction's future and would
        be skipped forever. This test failed intermittently before the fix,
        which is exactly how it would have behaved in production: a queue that
        mostly works.
        """
        job = self.env["analitix.job"].enqueue(
            "staff_match", {"event_ids": []}, store=self.store_one)
        self.assertEqual(job.state, "pending")
        self.env["analitix.job"]._cron_run()
        self.assertEqual(job.state, "done",
                         "a job enqueued in this transaction was never claimed")

    def test_a_future_job_is_not_run_early(self):
        job = self.env["analitix.job"].enqueue(
            "staff_match", {"event_ids": []}, delay_s=3600)
        self.env["analitix.job"]._cron_run()
        self.assertEqual(job.state, "pending")

    def test_queue_stats_report_the_backlog(self):
        self.env["analitix.job"].enqueue("staff_match", {"event_ids": []})
        stats = self.env["analitix.job"].queue_stats()
        self.assertGreaterEqual(stats["pending"], 1)


@tagged("post_install", "-at_install")
class TestAnomalyDetection(AnalitixCase):

    def test_a_device_far_above_its_own_baseline_is_flagged(self):
        device = self.device_one
        device.sudo().write({"baseline_hourly_events": 0.0})
        # A week of steady traffic — comfortably clear of the minimum history,
        # so the test is not sitting on the guard's boundary — then a burst.
        now = fields.Datetime.now()
        for hours_ago in range(2, 160):
            for _ in range(4):
                self.make_event(
                    device, "in", when=now - timedelta(hours=hours_ago))
        for _ in range(400):
            self.make_event(device, "in", when=now - timedelta(minutes=5))

        self.Device._cron_update_baselines()
        device.invalidate_recordset()
        self.assertGreater(device.baseline_hourly_events, 0.0)
        self.assertTrue(self.env["analitix.audit.log"].search_count([
            ("action", "=", "anomaly"),
        ]), "a tenfold volume spike went unnoticed")

    def test_a_brand_new_device_is_not_called_anomalous(self):
        """Day one traffic has no baseline to be abnormal against."""
        device = self.devices_three[0]
        now = fields.Datetime.now()
        for _ in range(50):
            self.make_event(device, "in", when=now - timedelta(minutes=5))

        # Counted for THIS device, not across the whole audit log: the cron
        # sweeps every active device, and on a database installed with demo data
        # the demo fleet legitimately raises its own entries. A global count
        # would make this test pass or fail on what else happens to be
        # installed, which is not what it is about.
        domain = [("action", "=", "anomaly"), ("model_name", "=", "analitix.device"),
                  ("res_id", "=", device.id)]
        before = self.env["analitix.audit.log"].search_count(domain)
        self.Device._cron_update_baselines()
        after = self.env["analitix.audit.log"].search_count(domain)
        self.assertEqual(before, after)


@tagged("post_install", "-at_install")
class TestBlindDevice(AnalitixCase):
    """The failure that looks exactly like health.

    An offline camera is visible: the heartbeat stops and everything flags it.
    A *blind* one is not. The agent is up, the heartbeat is punctual, the
    dashboard is green — and the shop has simply stopped being counted. A
    weekend can pass before anybody notices, and the figures for those days end
    up wrong rather than missing, which is worse: the conversion rate reads high
    because the tickets keep arriving and the visitors do not.
    """

    def setUp(self):
        super().setUp()
        self.store_one.write({
            "degraded_threshold_min": 2,
            "offline_threshold_min": 5,
            "blind_after_minutes": 120,
        })
        self.device_one._mark_seen()
        # A device with a real history, so there is something to be silent
        # against. Below the floor it is deliberately not judged at all.
        self.device_one.sudo().baseline_hourly_events = 25.0

    def _run(self):
        self.Device._cron_check_health()
        self.device_one.invalidate_recordset()

    def test_a_heartbeating_camera_that_sees_nothing_is_flagged(self):
        self.device_one.sudo().last_event_at = (
            fields.Datetime.now() - timedelta(hours=5))
        self._run()
        self.assertEqual(self.device_one.status, "online",
                         "the device is not offline — that is the whole point")
        self.assertTrue(self.device_one.blind_since,
                        "a camera that counted nobody for five hours went unflagged")

    def test_a_critical_blind_camera_reaches_a_person(self):
        self.store_one.alert_user_id = self.env.user.id
        self.device_one.critical = True
        self.device_one.sudo().last_event_at = (
            fields.Datetime.now() - timedelta(hours=5))
        self._run()
        activity = self.env["mail.activity"].search([
            ("res_model", "=", "analitix.device"),
            ("res_id", "=", self.device_one.id)])
        self.assertTrue(activity, "nobody was told the camera stopped seeing")

    def test_traffic_arriving_clears_it(self):
        self.device_one.sudo().last_event_at = (
            fields.Datetime.now() - timedelta(hours=5))
        self._run()
        self.assertTrue(self.device_one.blind_since)

        self.device_one.sudo().last_event_at = fields.Datetime.now()
        self._run()
        self.assertFalse(self.device_one.blind_since,
                         "it stayed flagged after crossings came back")

    def test_it_alerts_once_and_not_every_minute(self):
        """The health cron runs every minute. A camera blind since Friday must
        not raise an activity every minute until Monday."""
        self.store_one.alert_user_id = self.env.user.id
        self.device_one.critical = True
        self.device_one.sudo().last_event_at = (
            fields.Datetime.now() - timedelta(hours=5))
        for _ in range(4):
            self._run()
        self.assertEqual(
            self.env["mail.activity"].search_count([
                ("res_model", "=", "analitix.device"),
                ("res_id", "=", self.device_one.id)]), 1)

    def test_a_quiet_door_is_never_judged(self):
        """A service door that sees four people a day would trip this every
        lunchtime, and an alert that cries wolf is one nobody reads."""
        self.device_one.sudo().baseline_hourly_events = 0.4
        self.device_one.sudo().last_event_at = (
            fields.Datetime.now() - timedelta(hours=9))
        self._run()
        self.assertFalse(self.device_one.blind_since)

    def test_a_brand_new_device_is_not_called_blind(self):
        """No history means no normal to be silent against."""
        self.device_one.sudo().write(
            {"baseline_hourly_events": 0.0, "last_event_at": False})
        self._run()
        self.assertFalse(self.device_one.blind_since)

    def test_a_paused_store_is_left_alone(self):
        """Silence during a deliberate pause is expected, not a fault."""
        self.device_one.sudo().last_event_at = (
            fields.Datetime.now() - timedelta(hours=5))
        self.store_one.action_pause_capture()
        self._run()
        self.assertEqual(self.device_one.status, "disabled")
        self.assertFalse(self.device_one.blind_since)

    def test_an_offline_device_is_not_also_called_blind(self):
        """It is offline. Saying both would send the technician looking at a
        lens when the machine is simply down."""
        self.device_one.sudo().write({
            "last_heartbeat": fields.Datetime.now() - timedelta(minutes=60),
            "last_event_at": fields.Datetime.now() - timedelta(hours=5),
        })
        self._run()
        self.assertEqual(self.device_one.status, "offline")
        self.assertFalse(self.device_one.blind_since)
