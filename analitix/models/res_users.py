# -*- coding: utf-8 -*-
"""Store scoping for users — the backbone of tenant isolation (task 984, point 5).

Multi-company alone is not enough.  The business model puts several customer
stores on one Odoo instance, and two of those customers may sit under the same
company record for a franchise, or a single company may hold stores that
different managers must not see across.  So access is scoped by *store*, not
only by company.

The rule, implemented in ``security/analitix_rules.xml``:

* a user with no store assigned sees every store of their allowed companies —
  the single-store customer, which is most of them, needs no setup at all;
* a user with stores assigned sees **only** those, and nothing widens that: not
  a company switch, not a manager group, not a shared parent company.

That "empty means all" default is the one genuinely risky choice here, so it is
deliberate and it is tested: it keeps the common case zero-configuration, and
the moment an instance becomes multi-tenant the implementer assigns stores and
the door closes. ``tests/test_isolation.py`` proves the closed case with two
customers on one instance and checks for zero crossover.
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

    @property
    def SELF_READABLE_FIELDS(self):
        # A user may see which stores they are scoped to; being unable to would
        # make "why can't I see store B?" unanswerable without an admin.
        return super().SELF_READABLE_FIELDS + ["analitix_store_ids"]

    @api.model
    def _analitix_allowed_store_ids(self):
        """Store ids the current user may see, or ``None`` for 'all of theirs'."""
        stores = self.env.user.analitix_store_ids
        return stores.ids if stores else None
