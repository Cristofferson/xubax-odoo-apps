# -*- coding: utf-8 -*-
"""The purchase unit: a couple, a family, three friends — one buying decision.

Why this matters commercially: a store that counts four visitors and one ticket
reads a 25% conversion rate, when in fact one group came in and that group
bought. Its real conversion was 100%. Getting this wrong makes every family-
oriented retailer look like it is failing, and it is the single most common way
a footfall system lies to its owner.

The decision is frozen at the door, on purpose
----------------------------------------------
Grouping is decided by *who crossed the same door within a couple of seconds of
each other, shoulder to shoulder*, and never revisited. The tempting
alternative — regrouping people later by how close together they walk inside —
is worse in every way that matters:

* it is unstable: a couple who split up at the entrance and meet at the till
  would flip between one unit and two depending on when you looked;
* it makes the number un-auditable: the store's conversion rate for a past hour
  would change after the fact;
* it quietly merges strangers who happen to queue together.

A frozen decision can be wrong, but it is wrong once, visibly, and the same way
every time you ask.
"""
from datetime import timedelta

from odoo import api, fields, models, _


class AnalitixVisitGroup(models.Model):
    _name = "analitix.visit.group"
    _description = "Analitix Purchase Unit"
    _order = "entered_at desc, id desc"
    _rec_name = "display_name"

    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)
    door_id = fields.Many2one(
        "analitix.door", string="Door", index=True, ondelete="set null",
        help="The single door this unit was formed at. People arriving at two "
             "different entrances are never one unit, however close in time — "
             "they did not arrive together.")
    entered_at = fields.Datetime(
        string="Entered", required=True, index=True,
        default=lambda self: fields.Datetime.now())

    visitor_ids = fields.One2many(
        "analitix.visitor", "visit_group_id", string="Members")
    size = fields.Integer(
        string="Size", default=1, required=True, index=True,
        help="How many people crossed together. 1 means a lone shopper, which "
             "is most of them.")
    kind = fields.Selection(
        selection=[
            ("single", "Alone"),
            ("pair", "Pair"),
            ("group", "Group (3+)"),
        ],
        string="Type", compute="_compute_kind", store=True, index=True)

    _store_entered_idx = models.Index("(store_id, entered_at DESC)")

    @api.depends("size")
    def _compute_kind(self):
        for group in self:
            if group.size >= 3:
                group.kind = "group"
            elif group.size == 2:
                group.kind = "pair"
            else:
                group.kind = "single"

    @api.depends("size", "door_id", "entered_at")
    def _compute_display_name(self):
        for group in self:
            group.display_name = _(
                "%(size)s person(s) at %(door)s",
                size=group.size, door=group.door_id.name or _("unknown door"))

    # ------------------------------------------------------------------
    @api.model
    def assign(self, visitor, event):
        """Put ``visitor`` in a unit, creating one if nobody is waiting.

        The window is per store because "arriving together" is not a universal
        interval: a wide automatic door lets a couple through side by side in
        under a second, a narrow one makes them file through three seconds
        apart.
        """
        store = event.store_id
        if visitor.visit_group_id:
            return visitor.visit_group_id
        window = timedelta(seconds=store.group_window_seconds)
        existing = self.sudo().search([
            ("store_id", "=", store.id),
            ("door_id", "=", event.door_id.id),
            ("entered_at", ">=", event.event_time - window),
            ("entered_at", "<=", event.event_time + window),
        ], order="entered_at desc", limit=1)

        if existing and len(existing.visitor_ids) < store.group_max_size:
            existing.sudo().write({
                "visitor_ids": [(4, visitor.id)],
                "size": len(existing.visitor_ids) + 1,
            })
            return existing

        return self.sudo().create({
            "store_id": store.id,
            "door_id": event.door_id.id,
            "entered_at": event.event_time,
            "visitor_ids": [(6, 0, visitor.ids)],
            "size": 1,
        })
