# -*- coding: utf-8 -*-
"""Proof that nothing is pinned to one store's shape.

This is the file that guards the product's core commercial promise, so it is
written adversarially: every assertion is one that would fail if a developer
quietly hardcoded a door count, a threshold or a store.
"""
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged

from .common import AnalitixCase


@tagged("post_install", "-at_install")
class TestConfigurability(AnalitixCase):

    def test_stores_may_have_any_number_of_doors(self):
        self.assertEqual(self.store_one.door_count, 1)
        self.assertEqual(self.store_three.door_count, 3)

        # And a fourth can be added later without touching anything else.
        self.Door.create({
            "store_id": self.store_three.id, "name": "Loading Bay", "code": "L",
            "kind": "service", "counts_visitors": False,
        })
        self.assertEqual(self.store_three.door_count, 4)

    def test_counting_aggregates_across_every_door(self):
        """Visitors are summed over whatever doors exist, not over a fixed set."""
        self.make_event(self.device_one, "in")
        self.store_one.invalidate_recordset()
        self.assertEqual(self.store_one.visitors_in, 1)

        for device in self.devices_three[:2]:
            self.make_event(device, "in")
            self.make_event(device, "in")
        self.store_three.invalidate_recordset()
        self.assertEqual(self.store_three.visitors_in, 4)

    def test_non_counting_door_is_measured_but_excluded(self):
        """A service door's traffic is recorded and kept out of the count.

        Both halves matter: dropping the event would make the door invisible on
        the traffic report, and counting it would drag conversion down with
        traffic that was never a customer.
        """
        service_device = self.devices_three[2]
        self.assertFalse(service_device.door_id.counts_visitors)

        event = self.make_event(service_device, "in", counted=False)
        self.store_three.invalidate_recordset()

        self.assertEqual(self.store_three.visitors_in, 0)
        self.assertTrue(event.exists(), "the crossing must still be stored")

    def test_thresholds_are_per_store(self):
        """Two stores may hold different thresholds at the same time."""
        self.store_one.offline_threshold_min = 3
        self.store_three.offline_threshold_min = 30
        self.assertEqual(self.store_one.offline_threshold_min, 3)
        self.assertEqual(self.store_three.offline_threshold_min, 30)

        self.store_one.staff_match_threshold = 0.45
        self.store_three.staff_match_threshold = 0.70
        self.assertNotEqual(self.store_one.staff_match_threshold,
                            self.store_three.staff_match_threshold)

    def test_threshold_must_be_a_similarity(self):
        with self.assertRaises(ValidationError):
            self.store_one.staff_match_threshold = 1.5

    def test_offline_threshold_cannot_precede_degraded(self):
        with self.assertRaises(Exception):
            self.store_one.write({
                "degraded_threshold_min": 10, "offline_threshold_min": 2,
            })

    def test_device_cannot_point_at_another_stores_door(self):
        with self.assertRaises(UserError):
            self.Device.create({
                "name": "Confused camera", "device_uid": "confused",
                "store_id": self.store_one.id,
                "door_id": self.doors_three[0].id,
            })

    def test_register_belongs_to_one_store_only(self):
        """Otherwise the same tickets would be counted for two stores."""
        register = self.env["pos.config"].create({"name": "Test Register"})
        self.store_one.write({
            "match_mode": "registers", "register_ids": [(6, 0, register.ids)],
        })
        with self.assertRaises(ValidationError):
            self.store_three.write({
                "match_mode": "registers", "register_ids": [(6, 0, register.ids)],
            })

    def test_setup_wizard_builds_any_shape(self):
        """The wizard is what an implementer uses; it must not assume a count."""
        Setup = self.env["analitix.store.setup"]
        # The first shop in a database activates itself, so the wizard hands
        # over seven working keys. What happens to shop number two is the
        # subject of tests/test_activation.py, not of this one.
        self.env["analitix.store"].sudo().search([]).write({"activated": False})
        wizard = Setup.create({
            "name": "Wizard Seven",
            "code": "W7",
            "company_id": self.company.id,
            "tz": "UTC",
            "match_mode": "company",
            "door_ids": [(0, 0, {
                "name": "Door %d" % n, "code": "D%d" % n,
                "kind": "main" if n == 1 else "secondary",
            }) for n in range(1, 8)],
        })
        wizard.action_create_store()

        store = wizard.store_id
        self.assertEqual(store.door_count, 7)
        self.assertEqual(store.device_count, 7)
        # Each device got its own credential; a shared key could not be revoked
        # for one camera without killing the other six.
        hashes = store.device_ids.sudo().mapped("api_key_hash")
        self.assertEqual(len(set(hashes)), 7)
        self.assertIn("API key", wizard.credentials)

    def test_setup_wizard_refuses_a_store_with_no_door(self):
        wizard = self.env["analitix.store.setup"].create({
            "name": "Doorless", "company_id": self.company.id,
            "tz": "UTC", "match_mode": "company", "door_ids": [],
        })
        with self.assertRaises(UserError):
            wizard.action_create_store()

    def test_setup_wizard_refuses_registers_mode_with_no_register(self):
        """Silent 0% conversion is worse than an error at setup time."""
        wizard = self.env["analitix.store.setup"].create({
            "name": "No Registers", "company_id": self.company.id,
            "tz": "UTC", "match_mode": "registers",
            "door_ids": [(0, 0, {"name": "Main", "code": "M"})],
        })
        with self.assertRaises(UserError):
            wizard.action_create_store()
