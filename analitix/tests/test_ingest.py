# -*- coding: utf-8 -*-
"""The ingest endpoint, exercised over real HTTP.

These run as ``HttpCase`` rather than against the controller object directly,
because most of what is being tested — bearer parsing, status codes, the TLS
refusal, CSRF exemption — only exists at the HTTP layer. A unit test that called
the method would pass while the endpoint was broken.
"""
import json
import uuid as uuid_lib

from odoo import fields
from odoo.tests.common import HttpCase, tagged

INGEST = "/analitix/api/v1/events"
HEARTBEAT = "/analitix/api/v1/heartbeat"
CONFIG = "/analitix/api/v1/config"
STAFF = "/analitix/api/v1/staff_signatures"


@tagged("post_install", "-at_install")
class TestIngest(HttpCase):

    def setUp(self):
        super().setUp()
        self.store = self.env["analitix.store"].create({
            "name": "Ingest Store", "code": "IN1",
            "company_id": self.env.company.id,
            "match_mode": "company", "tz": "UTC",
        })
        self.door = self.env["analitix.door"].create({
            "store_id": self.store.id, "name": "Main", "code": "M",
        })
        # Contracted shop — see the note in tests/common.py; the gate
        # itself is tested in tests/test_activation.py.
        self.store.sudo().write({"activated": True})
        self.device = self.env["analitix.device"].create({
            "name": "Counter", "device_uid": "in1-main",
            "store_id": self.store.id, "door_id": self.door.id,
        })
        self.key = self.device._issue_key()
        self.env.cr.flush()

    # ------------------------------------------------------------------
    def _post(self, url, payload, key=None, secure=True):
        headers = {"Content-Type": "application/json"}
        if key is not False:
            headers["Authorization"] = "Bearer %s" % (key or self.key)
        if secure:
            # The test client speaks plain HTTP; this is the header nginx sets
            # in production and the controller trusts under proxy_mode.
            headers["X-Forwarded-Proto"] = "https"
        return self.url_open(url, data=json.dumps(payload), headers=headers)

    def _get(self, url, key=None, secure=True):
        headers = {}
        if key is not False:
            headers["Authorization"] = "Bearer %s" % (key or self.key)
        if secure:
            headers["X-Forwarded-Proto"] = "https"
        return self.url_open(url, headers=headers)

    @staticmethod
    def _event(**kw):
        payload = {
            "uuid": str(uuid_lib.uuid4()),
            "ts": fields.Datetime.now().isoformat(),
            "direction": "in",
            "count": 1,
        }
        payload.update(kw)
        return payload

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    def test_stores_a_batch(self):
        events = [self._event(), self._event(direction="out")]
        response = self._post(INGEST, {"events": events})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["stored"], 2)
        self.assertEqual(
            self.env["analitix.event"].search_count(
                [("store_id", "=", self.store.id)]), 2)

    def test_event_time_comes_from_the_edge_not_the_clock(self):
        """A replayed buffer must land on the hour it actually happened.

        This is the difference between an outage showing as a gap and an outage
        showing as an impossible spike the minute the link recovered.
        """
        past = fields.Datetime.subtract(fields.Datetime.now(), hours=5)
        self._post(INGEST, {"events": [self._event(ts=past.isoformat())]})
        stored = self.env["analitix.event"].search(
            [("store_id", "=", self.store.id)], limit=1)
        self.assertEqual(
            stored.event_time.replace(microsecond=0), past.replace(microsecond=0))

    # ------------------------------------------------------------------
    # Idempotency (task 982, point 2)
    # ------------------------------------------------------------------
    def test_the_same_uuid_is_stored_once(self):
        event = self._event()
        first = self._post(INGEST, {"events": [event]})
        second = self._post(INGEST, {"events": [event]})

        self.assertEqual(first.json()["stored"], 1)
        self.assertEqual(second.json()["stored"], 0)
        self.assertEqual(second.json()["duplicates"], 1)
        self.assertEqual(
            self.env["analitix.event"].search_count(
                [("store_id", "=", self.store.id)]), 1,
            "a retried batch must not inflate the visitor count")

    def test_a_duplicate_is_acknowledged_so_the_agent_stops_retrying(self):
        event = self._event()
        self._post(INGEST, {"events": [event]})
        body = self._post(INGEST, {"events": [event]}).json()
        self.assertIn(event["uuid"], body["acknowledged"])

    def test_a_repeat_inside_one_batch_is_collapsed(self):
        event = self._event()
        body = self._post(INGEST, {"events": [event, event]}).json()
        self.assertEqual(body["stored"], 1)
        self.assertEqual(body["duplicates"], 1)

    # ------------------------------------------------------------------
    # Partial success
    # ------------------------------------------------------------------
    def test_one_bad_row_does_not_reject_the_batch(self):
        good = self._event()
        body = self._post(INGEST, {"events": [
            good,
            self._event(direction="sideways"),
            self._event(ts="not-a-date"),
            {"no_uuid": True},
        ]}).json()
        self.assertEqual(body["stored"], 1)
        reasons = {row["reason"] for row in body["rejected"]}
        self.assertEqual(
            reasons, {"bad_direction", "bad_timestamp", "missing_uuid"})

    def test_an_event_without_a_uuid_is_refused(self):
        """No uuid means no idempotency, so it cannot be accepted safely."""
        body = self._post(INGEST, {"events": [{
            "ts": fields.Datetime.now().isoformat(), "direction": "in",
        }]}).json()
        self.assertEqual(body["stored"], 0)
        self.assertEqual(body["rejected"][0]["reason"], "missing_uuid")

    def test_oversized_batches_are_refused(self):
        events = [self._event() for _ in range(1001)]
        response = self._post(INGEST, {"events": events})
        self.assertEqual(response.status_code, 413)

    def test_malformed_json_is_a_400(self):
        response = self.url_open(
            INGEST, data="{not json",
            headers={"Authorization": "Bearer %s" % self.key,
                     "Content-Type": "application/json",
                     "X-Forwarded-Proto": "https"})
        self.assertEqual(response.status_code, 400)

    # ------------------------------------------------------------------
    # Heartbeat and config
    # ------------------------------------------------------------------
    def test_heartbeat_brings_a_device_online(self):
        self.assertEqual(self.device.status, "never_seen")
        response = self._post(HEARTBEAT, {
            "agent_version": "1.2.3", "queue_size": 4})
        self.assertEqual(response.status_code, 200)
        self.device.invalidate_recordset()
        self.assertEqual(self.device.status, "online")
        self.assertEqual(self.device.agent_version, "1.2.3")
        self.assertEqual(self.device.edge_queue_size, 4)

    def test_heartbeat_hands_back_the_stores_interval(self):
        """Retuning a fleet is a field change in Odoo, not a site visit."""
        self.store.heartbeat_interval_s = 120
        body = self._post(HEARTBEAT, {}).json()
        self.assertEqual(body["heartbeat_interval_s"], 120)

    def test_config_is_scoped_to_the_devices_own_store(self):
        body = self._get(CONFIG).json()
        self.assertEqual(body["store"]["id"], self.store.id)
        self.assertEqual(body["door"]["name"], "Main")
        self.assertEqual(body["device"]["uid"], "in1-main")
