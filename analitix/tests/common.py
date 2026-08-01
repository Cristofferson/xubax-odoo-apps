# -*- coding: utf-8 -*-
"""Shared fixtures.

The master instruction requires every phase to be proved against **at least two
different store shapes**, so that nothing quietly assumes "the door".  The base
case here is therefore not one store but two: a one-door boutique and a
three-door mall unit whose third door does not count visitors.  Every test that
touches counting runs against both.
"""
import uuid as uuid_lib

from odoo import fields
from odoo.tests.common import TransactionCase


class AnalitixCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Store = cls.env["analitix.store"]
        cls.Door = cls.env["analitix.door"]
        cls.Device = cls.env["analitix.device"]
        cls.Event = cls.env["analitix.event"]
        cls.Signature = cls.env["analitix.staff.signature"]
        cls.company = cls.env.company

        # --- shape 1: a single-door boutique ---
        cls.store_one = cls.Store.create({
            "name": "Test Boutique",
            "code": "T1",
            "company_id": cls.company.id,
            "match_mode": "company",
            "area_sqm": 80.0,
            "tz": "UTC",
        })
        cls.door_one = cls.Door.create({
            "store_id": cls.store_one.id, "name": "Main", "code": "M",
        })
        cls.device_one = cls.Device.create({
            "name": "Main counter", "device_uid": "t1-main",
            "store_id": cls.store_one.id, "door_id": cls.door_one.id,
        })
        cls.key_one = cls.device_one._issue_key()

        # --- shape 2: three doors, one of which is staff-only ---
        cls.store_three = cls.Store.create({
            "name": "Test Mall Unit",
            "code": "T3",
            "company_id": cls.company.id,
            "match_mode": "company",
            "area_sqm": 240.0,
            "tz": "UTC",
        })
        cls.doors_three = cls.Door.create([
            {"store_id": cls.store_three.id, "name": "Street", "code": "S"},
            {"store_id": cls.store_three.id, "name": "Gallery", "code": "G",
             "kind": "mall"},
            {"store_id": cls.store_three.id, "name": "Service", "code": "V",
             "kind": "service", "counts_visitors": False},
        ])
        cls.devices_three = cls.Device.create([
            {"name": "Street counter", "device_uid": "t3-street",
             "store_id": cls.store_three.id, "door_id": cls.doors_three[0].id},
            {"name": "Gallery counter", "device_uid": "t3-gallery",
             "store_id": cls.store_three.id, "door_id": cls.doors_three[1].id},
            {"name": "Service counter", "device_uid": "t3-service",
             "store_id": cls.store_three.id, "door_id": cls.doors_three[2].id},
        ])
        cls.keys_three = [d._issue_key() for d in cls.devices_three]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def make_event(self, device, direction="in", when=None, count=1, **extra):
        """Create a crossing straight through the ORM, bypassing HTTP."""
        vals = {
            "uuid": str(uuid_lib.uuid4()),
            "device_id": device.id,
            "door_id": device.door_id.id,
            "store_id": device.store_id.id,
            "direction": direction,
            "count": count,
            "event_time": when or fields.Datetime.now(),
        }
        vals.update(extra)
        return self.Event.create(vals)

    @staticmethod
    def fake_vector(seed, dim=32):
        """A deterministic pseudo-embedding.

        Real vectors come from buffalo_l, which this addon never runs. What the
        tests actually need is only that two vectors built from the same seed
        match and two from different seeds do not — so an arithmetic stand-in is
        both sufficient and far faster than loading a face model.
        """
        return [((seed * 37 + i * 13) % 100) / 100.0 - 0.5 for i in range(dim)]
