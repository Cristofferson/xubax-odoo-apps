# -*- coding: utf-8 -*-
"""Tenant isolation, proved rather than assumed (task 984, point 5).

The business model puts several paying customers on one Odoo instance.  That
makes "user of store A can never see store B" a load-bearing claim, and task 984
is explicit that it must be *tested with two stores of different customers and
zero crossover verified* — not asserted in a comment.

So this file builds two customers on one instance, gives each a user, and then
tries, from each user's own environment, to reach the other's data through every
route the ORM offers: search, read, browse, aggregation, the dashboards and the
raw event log.
"""
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTenantIsolation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env["res.company"]
        Store = cls.env["analitix.store"]
        Users = cls.env["res.users"].with_context(no_reset_password=True)

        # Two genuinely separate customers sharing one instance.
        cls.company_a = Company.create({"name": "Customer A SA"})
        cls.company_b = Company.create({"name": "Customer B SA"})

        cls.store_a = Store.create({
            "name": "A — Downtown", "code": "A1", "tz": "UTC",
            "company_id": cls.company_a.id, "match_mode": "company"})
        cls.store_b = Store.create({
            "name": "B — Riverside", "code": "B1", "tz": "UTC",
            "company_id": cls.company_b.id, "match_mode": "company"})

        for store in (cls.store_a, cls.store_b):
            door = cls.env["analitix.door"].create({
                "store_id": store.id, "name": "Main", "code": "M"})
            store.sudo().write({"activated": True})
            device = cls.env["analitix.device"].create({
                "name": "Counter", "device_uid": "%s-main" % store.code.lower(),
                "store_id": store.id, "door_id": door.id})
            cls.env["analitix.event"].create({
                "uuid": "iso-%s" % store.code,
                "device_id": device.id, "door_id": door.id,
                "store_id": store.id, "direction": "in", "count": 1})

        manager_group = cls.env.ref("analitix.group_manager")

        # Deliberately a MANAGER, not a plain user: the rules are global, so a
        # permission group must not be a way around tenancy.
        cls.user_a = Users.create({
            "name": "Manager A", "login": "analitix_iso_a@example.com",
            "company_id": cls.company_a.id,
            "company_ids": [(6, 0, [cls.company_a.id])],
            "group_ids": [(4, manager_group.id)],
            "analitix_store_ids": [(6, 0, [cls.store_a.id])],
        })
        cls.user_b = Users.create({
            "name": "Manager B", "login": "analitix_iso_b@example.com",
            "company_id": cls.company_b.id,
            "company_ids": [(6, 0, [cls.company_b.id])],
            "group_ids": [(4, manager_group.id)],
            "analitix_store_ids": [(6, 0, [cls.store_b.id])],
        })

    # ------------------------------------------------------------------
    def test_a_manager_sees_only_their_own_store(self):
        visible = self.env["analitix.store"].with_user(self.user_a).search([])
        self.assertEqual(visible, self.store_a)
        self.assertNotIn(self.store_b, visible)

    def test_the_isolation_is_symmetric(self):
        visible = self.env["analitix.store"].with_user(self.user_b).search([])
        self.assertEqual(visible, self.store_b)

    def test_naming_the_other_store_explicitly_still_fails(self):
        """Filtering is not enough; a direct read must be refused too."""
        with self.assertRaises(AccessError):
            self.env["analitix.store"].with_user(self.user_a).browse(
                self.store_b.id).read(["name"])

    def test_a_domain_that_asks_for_everything_returns_only_ours(self):
        found = self.env["analitix.store"].with_user(self.user_a).search(
            [("id", "in", [self.store_a.id, self.store_b.id])])
        self.assertEqual(found, self.store_a)

    def test_doors_devices_and_events_are_scoped_too(self):
        """The store record is not the only way in."""
        for model in ("analitix.door", "analitix.device", "analitix.event"):
            records = self.env[model].with_user(self.user_a).search([])
            other = records.filtered(lambda r: r.store_id == self.store_b)
            self.assertFalse(
                other, "%s leaked store B's rows to user A" % model)

    def test_aggregates_do_not_leak_across_customers(self):
        """A read_group is the classic hole: totals that include hidden rows."""
        grouped = self.env["analitix.event"].with_user(self.user_a)._read_group(
            [], groupby=["store_id"], aggregates=["__count"])
        stores = [store for store, _count in grouped]
        self.assertNotIn(self.store_b, stores)

    def test_the_dashboards_are_scoped(self):
        for model in ("analitix.hourly", "analitix.door.hourly"):
            rows = self.env[model].with_user(self.user_a).search([])
            self.assertFalse(
                rows.filtered(lambda r: r.store_id == self.store_b),
                "%s leaked store B into store A's dashboard" % model)

    def test_a_manager_cannot_write_into_the_other_customer(self):
        with self.assertRaises(AccessError):
            self.env["analitix.store"].with_user(self.user_a).browse(
                self.store_b.id).write({"name": "hijacked"})

    def test_staff_signatures_do_not_cross(self):
        employee = self.env["hr.employee"].create({
            "name": "B's employee", "company_id": self.company_b.id})
        self.env["analitix.staff.signature"].create({
            "store_id": self.store_b.id, "employee_id": employee.id,
            "embedding_dim": 4,
            "embedding": self.env["analitix.crypto"].encrypt_vector(
                [0.1, 0.2, 0.3, 0.4]),
        })
        visible = self.env["analitix.staff.signature"].with_user(
            self.user_a).search([])
        self.assertFalse(visible)

    def test_an_unscoped_user_still_cannot_cross_companies(self):
        """Empty store list means 'all of *my companies*', not 'all stores'.

        This is the risky half of the convenience default, so it is the half
        worth proving: a user with no explicit scope must still be held by the
        company boundary.
        """
        self.user_a.analitix_store_ids = [(5, 0, 0)]
        visible = self.env["analitix.store"].with_user(self.user_a).search([])
        self.assertIn(self.store_a, visible)
        self.assertNotIn(self.store_b, visible)

    def test_two_stores_of_one_company_can_be_split_between_users(self):
        """A franchise: same company record, two operators who must not mix."""
        second = self.env["analitix.store"].create({
            "name": "A — Second Branch", "code": "A2", "tz": "UTC",
            "company_id": self.company_a.id, "match_mode": "company"})
        visible = self.env["analitix.store"].with_user(self.user_a).search([])
        self.assertEqual(visible, self.store_a)
        self.assertNotIn(second, visible)
