# -*- coding: utf-8 -*-
"""Credentials, encryption and the kill switch (task 984)."""
import json
import uuid as uuid_lib

from odoo import fields
from odoo.tests.common import HttpCase, TransactionCase, tagged

from .common import AnalitixCase

INGEST = "/analitix/api/v1/events"
STAFF = "/analitix/api/v1/staff_signatures"


@tagged("post_install", "-at_install")
class TestCredentials(HttpCase):

    def setUp(self):
        super().setUp()
        self.store = self.env["analitix.store"].create({
            "name": "Key Store", "code": "K1", "tz": "UTC",
            "company_id": self.env.company.id, "match_mode": "company",
        })
        self.door = self.env["analitix.door"].create({
            "store_id": self.store.id, "name": "Main", "code": "M"})
        # Contracted shop — see the note in tests/common.py; the gate
        # itself is tested in tests/test_activation.py.
        self.store.sudo().write({"activated": True})
        self.device = self.env["analitix.device"].create({
            "name": "Counter", "device_uid": "k1-main",
            "store_id": self.store.id, "door_id": self.door.id})
        self.key = self.device._issue_key()

        # A second store with its own device, to prove keys do not cross.
        self.other_store = self.env["analitix.store"].create({
            "name": "Other Store", "code": "K2", "tz": "UTC",
            "company_id": self.env.company.id, "match_mode": "company"})
        self.other_store.sudo().write({"activated": True})
        self.other_device = self.env["analitix.device"].create({
            "name": "Other counter", "device_uid": "k2-main",
            "store_id": self.other_store.id})
        self.other_key = self.other_device._issue_key()
        self.env.cr.flush()

    def _post(self, payload, key=None, secure=True, url=INGEST):
        headers = {"Content-Type": "application/json"}
        if key is not False:
            headers["Authorization"] = "Bearer %s" % (key or self.key)
        if secure:
            headers["X-Forwarded-Proto"] = "https"
        return self.url_open(url, data=json.dumps(payload), headers=headers)

    @staticmethod
    def _event():
        return {"uuid": str(uuid_lib.uuid4()),
                "ts": fields.Datetime.now().isoformat(), "direction": "in"}

    # ------------------------------------------------------------------
    def test_the_key_is_never_stored_in_the_clear(self):
        stored = self.device.sudo().api_key_hash
        self.assertTrue(stored)
        self.assertNotIn(self.key, stored)
        self.assertNotEqual(stored, self.key)
        # And it is not hiding in any other field either.
        dumped = json.dumps(self.device.sudo().read()[0], default=str)
        self.assertNotIn(self.key, dumped)

    def test_a_missing_key_is_rejected(self):
        response = self._post({"events": [self._event()]}, key=False)
        self.assertEqual(response.status_code, 401)

    def test_a_wrong_key_is_rejected(self):
        response = self._post({"events": [self._event()]}, key="alx_nonsense")
        self.assertEqual(response.status_code, 401)

    def test_failures_do_not_reveal_why(self):
        """Distinguishing 'unknown' from 'revoked' maps out the fleet."""
        unknown = self._post({"events": [self._event()]}, key="alx_nope").json()
        self.device.action_revoke_key()
        revoked = self._post({"events": [self._event()]}).json()
        self.assertEqual(unknown["error"], revoked["error"])

    def test_rotation_kills_the_previous_key_immediately(self):
        old_key = self.key
        self.device.action_rotate_key()
        response = self._post({"events": [self._event()]}, key=old_key)
        self.assertEqual(response.status_code, 401)

    def test_revocation_needs_no_access_to_the_hardware(self):
        self.assertEqual(
            self._post({"events": [self._event()]}).status_code, 200)
        self.device.action_revoke_key()
        self.assertEqual(
            self._post({"events": [self._event()]}).status_code, 401)

    def test_an_archived_device_cannot_post(self):
        self.device.active = False
        self.assertEqual(
            self._post({"events": [self._event()]}).status_code, 401)

    def test_a_key_only_reaches_its_own_store(self):
        """The critical property: a stolen key is worth one store, not the fleet."""
        self._post({"events": [self._event()]}, key=self.other_key)
        events = self.env["analitix.event"].search(
            [("store_id", "=", self.other_store.id)])
        self.assertTrue(events)
        self.assertEqual(
            self.env["analitix.event"].search_count(
                [("store_id", "=", self.store.id)]), 0,
            "store B's key must never write into store A")

    def test_plaintext_http_is_refused(self):
        response = self._post({"events": [self._event()]}, secure=False)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "tls_required")

    def test_plaintext_can_be_allowed_deliberately_for_a_lab(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "analitix.allow_insecure_ingest", "1")
        response = self._post({"events": [self._event()]}, secure=False)
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # Kill switch (task 984, point 8)
    # ------------------------------------------------------------------
    def test_kill_switch_stops_ingest_at_once(self):
        self.assertEqual(
            self._post({"events": [self._event()]}).status_code, 200)
        self.store.action_pause_capture()
        response = self._post({"events": [self._event()]})
        self.assertEqual(response.status_code, 423)
        self.assertEqual(response.json()["error"], "capture_paused")

    def test_kill_switch_is_reversible_from_the_ui(self):
        self.store.action_pause_capture()
        self.store.action_resume_capture()
        self.assertEqual(
            self._post({"events": [self._event()]}).status_code, 200)

    def test_pausing_one_store_leaves_the_others_running(self):
        self.store.action_pause_capture()
        self.assertEqual(
            self._post({"events": [self._event()]}, key=self.other_key).status_code,
            200)

    def test_kill_switch_use_is_audited(self):
        self.store.action_pause_capture()
        entry = self.env["analitix.audit.log"].search([
            ("action", "=", "kill_switch"), ("store_id", "=", self.store.id),
        ], limit=1)
        self.assertTrue(entry)
        self.assertEqual(entry.user_id, self.env.user)

    def test_rejected_credentials_are_audited(self):
        self._post({"events": [self._event()]}, key="alx_intruder")
        self.assertTrue(self.env["analitix.audit.log"].search_count(
            [("action", "=", "auth_failure")]))


@tagged("post_install", "-at_install")
class TestEncryptionAndStaff(AnalitixCase):

    def test_embeddings_are_encrypted_at_rest(self):
        vector = self.fake_vector(1)
        signature = self.Signature.create({
            "store_id": self.store_one.id,
            "employee_id": self.env["hr.employee"].create({"name": "Ana"}).id,
            "embedding": self.env["analitix.crypto"].encrypt_vector(vector),
            "embedding_dim": len(vector),
        })
        stored = signature.sudo().embedding
        # A raw read of the column must not yield anything vector-shaped.
        self.assertNotIn("0.", stored[:40])
        self.assertNotIn(str(vector[0]), stored)

    def test_an_encrypted_vector_round_trips(self):
        crypto = self.env["analitix.crypto"]
        vector = self.fake_vector(7)
        restored = crypto.decrypt_vector(crypto.encrypt_vector(vector))
        self.assertEqual(len(restored), len(vector))
        for original, back in zip(vector, restored):
            self.assertAlmostEqual(original, back, places=5)

    def test_a_corrupt_vector_degrades_instead_of_exploding(self):
        """One bad row must not take down a whole matching batch."""
        self.assertEqual(
            self.env["analitix.crypto"].decrypt_vector("not-a-token"), [])

    def test_staff_are_excluded_from_the_count(self):
        employee = self.env["hr.employee"].create({"name": "Beto"})
        self.Signature.enrol(self.store_one, employee, self.fake_vector(3))

        signature_id, employee_id, score = self.Signature.match(
            self.store_one, self.fake_vector(3))
        self.assertEqual(employee_id, employee.id)
        self.assertGreater(score, self.store_one.staff_match_threshold)

    def test_a_stranger_is_not_matched_to_staff(self):
        employee = self.env["hr.employee"].create({"name": "Carla"})
        self.Signature.enrol(self.store_one, employee, self.fake_vector(3))
        _sig, matched, _score = self.Signature.match(
            self.store_one, [-v for v in self.fake_vector(3)])
        self.assertIsNone(matched)

    def test_signatures_do_not_leak_between_stores(self):
        """An employee enrolled in store A is not excluded from store B."""
        employee = self.env["hr.employee"].create({"name": "Dani"})
        self.Signature.enrol(self.store_one, employee, self.fake_vector(5))
        _sig, matched, _score = self.Signature.match(
            self.store_three, self.fake_vector(5))
        self.assertIsNone(matched)

    def test_disabling_exclusion_stops_matching(self):
        employee = self.env["hr.employee"].create({"name": "Eva"})
        self.Signature.enrol(self.store_one, employee, self.fake_vector(9))
        self.store_one.exclude_staff = False
        _sig, matched, _score = self.Signature.match(
            self.store_one, self.fake_vector(9))
        self.assertIsNone(matched)

    def test_removing_a_signature_takes_effect_immediately(self):
        """A stale cache would keep excluding someone who was just removed."""
        employee = self.env["hr.employee"].create({"name": "Fito"})
        signature = self.Signature.enrol(
            self.store_one, employee, self.fake_vector(11))
        self.Signature.match(self.store_one, self.fake_vector(11))  # warm cache
        signature.unlink()
        _sig, matched, _score = self.Signature.match(
            self.store_one, self.fake_vector(11))
        self.assertIsNone(matched)


@tagged("post_install", "-at_install")
class TestAuditLog(TransactionCase):

    def test_audit_entries_cannot_be_edited_or_deleted(self):
        from odoo.exceptions import UserError
        entry = self.env["analitix.audit.log"].log(
            action="read_sensitive", note="test")
        with self.assertRaises(UserError):
            entry.note = "tampered"
        with self.assertRaises(UserError):
            entry.unlink()
