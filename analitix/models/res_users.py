# -*- coding: utf-8 -*-
"""Store scoping for users — the backbone of tenant isolation (task 984, point 5).

Multi-company alone is not enough.  The business model puts several customer
stores on one Odoo instance, and two of those customers may sit under the same
company record for a franchise, or a single company may hold stores that
different managers must not see across.  So access is scoped by *store*, not
only by company.

The rule, implemented in ``security/analitix_rules.xml``:

* a user with no store **and no region** assigned sees every store of their
  allowed companies — the single-store customer, which is most of them, needs
  no setup at all;
* a user with stores or regions assigned sees **only** those, and nothing
  widens that: not a company switch, not a manager group, not a shared parent
  company.

That "empty means all" default is the one genuinely risky choice here, so it is
deliberate and it is tested: it keeps the common case zero-configuration, and
the moment an instance becomes multi-tenant the implementer assigns stores and
the door closes. ``tests/test_isolation.py`` proves the closed case with two
customers on one instance and checks for zero crossover.

Phase 7 adds regions on top. A regional manager is given a *region*, not a list
of twenty stores that somebody has to remember to extend when the twenty-first
opens — which is exactly the maintenance nobody does, and the reason stale
access lists outlive the people they were written for.
"""
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    analitix_store_ids = fields.Many2many(
        "analitix.store", relation="analitix_store_user_rel",
        column1="user_id", column2="store_id", string="Analitix Stores",
        help="Restrict this user to these stores. Leave empty to give access "
             "to every store of the companies they already belong to — right "
             "for a single-store customer, wrong for a shared instance.")
    analitix_region_ids = fields.Many2many(
        "analitix.region", relation="analitix_region_user_rel",
        column1="user_id", column2="region_id", string="Analitix Regions",
        help="Scope this user to whole regions. Every store in them is "
             "included, including the ones that open next year — which is the "
             "point: a list of individual stores goes stale the first time the "
             "chain grows and nobody updates it.")

    analitix_scope_store_ids = fields.Many2many(
        "analitix.store", string="Effective Store Scope",
        compute="_compute_analitix_scope", compute_sudo=True,
        help="The stores this user can actually reach: the ones assigned "
             "directly plus every store of their regions. The record rules "
             "read this one field, so the two ways of granting access can "
             "never disagree with each other.")
    analitix_scoped = fields.Boolean(
        string="Analitix Scope Restricted", compute="_compute_analitix_scope",
        compute_sudo=True,
        help="True when this user has been given specific stores or regions, "
             "and is therefore locked to them.")

    @api.depends("analitix_store_ids", "analitix_region_ids",
                 "analitix_region_ids.store_ids")
    def _compute_analitix_scope(self):
        """Resolve the two ways of granting access into one list.

        Deliberately not stored. A stored version would have to be invalidated
        whenever a store changes region or a region gains one, and a scope cache
        that goes stale is a user still seeing a branch they were moved off —
        the exact failure this file exists to prevent. The compute is cheap, and
        Odoo caches it for the length of the request anyway.
        """
        for user in self:
            user.analitix_scope_store_ids = (
                user.analitix_store_ids | user.analitix_region_ids.store_ids)
            # Read the raw fields, not the union above: a user given a region
            # that happens to hold no stores yet is still a *restricted* user,
            # and must not fall through to "sees everything".
            user.analitix_scoped = bool(
                user.analitix_store_ids or user.analitix_region_ids)

    @property
    def SELF_READABLE_FIELDS(self):
        # A user may see which stores they are scoped to; being unable to would
        # make "why can't I see store B?" unanswerable without an admin.
        return super().SELF_READABLE_FIELDS + [
            "analitix_store_ids", "analitix_region_ids",
            "analitix_scope_store_ids", "analitix_scoped",
        ]

    @api.model
    def _analitix_allowed_store_ids(self):
        """Store ids the current user may see, or ``None`` for 'all of theirs'."""
        user = self.env.user
        return user.analitix_scope_store_ids.ids if user.analitix_scoped else None
