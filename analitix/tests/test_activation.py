# -*- coding: utf-8 -*-
"""The one gate the commercial terms put on the software.

These tests are written from both sides on purpose. Half of them prove the
gate holds — a second shop cannot give itself a key, a code from another shop
or another database is refused. The other half prove the gate does *not* creep
into places we promised it would never reach: a store already collecting keeps
collecting, and a billing state never takes activation away.
"""
import base64
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import AnalitixCase


def sign(private_key, payload):
    return base64.b64encode(private_key.sign(payload.encode())).decode()


@tagged("post_install", "-at_install")
class TestActivation(AnalitixCase):
    """A shop has to be activated before its cameras get a key."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A throwaway keypair, and the module pointed at its public half, so the
        # test never needs the real signing key — which is not in this repo and
        # must not be.
        cls.signing_key = ed25519.Ed25519PrivateKey.generate()
        public = cls.signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)
        cls.public_b64 = base64.b64encode(public).decode()

    def setUp(self):
        super().setUp()
        patcher = patch(
            "odoo.addons.analitix.models.analitix_activation."
            "ACTIVATION_PUBLIC_KEY", self.public_b64)
        patcher.start()
        self.addCleanup(patcher.stop)

    def uuid(self):
        return self.env["ir.config_parameter"].sudo().get_param("database.uuid")

    def make_store(self, code):
        return self.env["analitix.store"].create({"name": code, "code": code})

    # ------------------------------------------------------------------
    def test_the_first_shop_can_activate_itself(self):
        """Otherwise the trial the listing promises would be a lie."""
        self.env["analitix.store"].sudo().search([]).write({"activated": False})
        store = self.make_store("SOLO-01")
        store.action_activate_trial()
        self.assertTrue(store.activated)
        self.assertEqual(store.activation_token, "TRIAL")

    def test_the_second_shop_cannot_activate_itself(self):
        self.env["analitix.store"].sudo().search([]).write({"activated": False})
        first = self.make_store("UNO-01")
        first.action_activate_trial()

        second = self.make_store("DOS-02")
        with self.assertRaises(UserError):
            second.action_activate_trial()
        self.assertFalse(second.activated)

    def test_a_valid_code_activates_the_shop_it_was_issued_for(self):
        store = self.make_store("REAL-07")
        store.activation_code_input = sign(
            self.signing_key, "%s:REAL-07" % self.uuid())
        store.action_activate_store()
        self.assertTrue(store.activated)
        self.assertFalse(store.activation_code_input,
                         "the pasted code should be cleared once it is spent")

    def test_a_code_issued_for_another_shop_is_refused(self):
        other = self.make_store("OTRA-08")
        target = self.make_store("REAL-09")
        target.activation_code_input = sign(
            self.signing_key, "%s:%s" % (self.uuid(), other.code))
        with self.assertRaises(UserError):
            target.action_activate_store()
        self.assertFalse(target.activated)

    def test_a_code_from_another_database_is_refused(self):
        """A restored copy of this database must not carry activations across."""
        store = self.make_store("REAL-10")
        store.activation_code_input = sign(
            self.signing_key, "00000000-dead-beef-0000-000000000000:REAL-10")
        with self.assertRaises(UserError):
            store.action_activate_store()
        self.assertFalse(store.activated)

    def test_rubbish_is_refused_without_blowing_up(self):
        store = self.make_store("REAL-11")
        for junk in ("", "   ", "no-es-base64!!", "aGVsbG8="):
            store.activation_code_input = junk
            with self.assertRaises(UserError):
                store.action_activate_store()
        self.assertFalse(store.activated)

    # ------------------------------------------------------------------
    def test_a_device_on_an_unactivated_shop_is_created_without_a_key(self):
        """The gate withholds the key; it does not blow up the form.

        Devices are created inside the setup wizard together with the shop and
        its doors, so raising here would leave somebody half way through a form
        with nothing to show for it.
        """
        store = self.make_store("SINACT-12")
        device = self.env["analitix.device"].create({
            "name": "Puerta", "device_uid": "sinact-12-door",
            "store_id": store.id, "role": "door_counter"})
        self.assertTrue(device.exists())
        self.assertFalse(device.sudo().api_key_hash,
                         "an unactivated shop must not get a working key")

    def test_the_setup_wizard_finishes_for_an_unactivated_shop(self):
        """It must hand over a shop, not an exception half way through."""
        wizard = self.env["analitix.store.setup"].create({
            "name": "Segunda Sucursal", "code": "SEG-16",
            "company_id": self.env.company.id, "tz": "UTC",
            "match_mode": "company",
            "door_ids": [(0, 0, {"name": "Main", "code": "M"})],
        })
        wizard.action_create_store()

        store = wizard.store_id
        self.assertTrue(store, "the shop is created even without activation")
        self.assertEqual(store.device_count, 1)
        self.assertFalse(store.device_ids.sudo().mapped("api_key_hash")[0])
        self.assertIn("not activated yet", wizard.credentials)
        self.assertIn(store.activation_request, wizard.credentials)

    def test_asking_for_a_key_outright_says_why_it_is_refused(self):
        store = self.make_store("SINACT-15")
        device = self.env["analitix.device"].create({
            "name": "Puerta", "device_uid": "sinact-15-door",
            "store_id": store.id, "role": "door_counter"})
        with self.assertRaises(UserError):
            device.action_rotate_key()

    def test_a_device_on_an_activated_shop_gets_its_key(self):
        store = self.make_store("CONACT-13")
        store.activation_code_input = sign(
            self.signing_key, "%s:CONACT-13" % self.uuid())
        store.action_activate_store()
        device = self.env["analitix.device"].create({
            "name": "Puerta", "device_uid": "conact-13-door",
            "store_id": store.id, "role": "door_counter"})
        self.assertTrue(device.sudo().api_key_hash)

    def test_the_gate_is_at_the_key_and_never_at_ingest(self):
        """The promise: a camera already sending keeps sending.

        If this ever fails, somebody moved the check into the ingest path and
        a billing problem can now blind a customer's shop.
        """
        import odoo.addons.analitix as addon
        with open(addon.__path__[0] + "/controllers/api.py",
                  encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("activated", source,
                         "ingest must not consult the activation flag")
        self.assertNotIn("_ensure_activated", source)

    def test_billing_state_never_withdraws_activation(self):
        store = self.make_store("PAGO-14")
        store.activation_code_input = sign(
            self.signing_key, "%s:PAGO-14" % self.uuid())
        store.action_activate_store()
        store.write({"subscription_state": "cancelled"})
        self.assertTrue(store.activated,
                        "cancelling the subscription must not deactivate a shop")
