# -*- coding: utf-8 -*-
"""A door is one entrance of a store.

A store has as many as it has — one corner shop, three for a mall unit with a
street door, a mall door and a service door.  Nothing in this addon may assume
a number.  Every crossing carries the door it happened at, so traffic can be
read per door while conversion stays at store level (a ticket belongs to the
store, not to whichever door the customer happened to use).
"""
from odoo import api, fields, models, _


class AnalitixDoor(models.Model):
    _name = "analitix.door"
    _description = "Analitix Store Door"
    _order = "store_id, sequence, id"

    name = fields.Char(
        required=True,
        help="Free-form name the staff of this store would use: "
             "'North Entrance', 'Mall Door', 'Service Door'.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)
    code = fields.Char(
        string="Reference", copy=False,
        help="Short code used in device UIDs, e.g. 'N' for the north door.")
    kind = fields.Selection(
        selection=[
            ("main", "Main entrance"),
            ("secondary", "Secondary entrance"),
            ("mall", "Mall / gallery entrance"),
            ("service", "Service / staff entrance"),
            ("emergency", "Emergency exit"),
        ],
        string="Door Type", default="main", required=True,
        help="Informational, but it drives sensible defaults: a service door "
             "is where staff traffic concentrates, an emergency exit normally "
             "produces exits only.")
    counts_visitors = fields.Boolean(
        string="Counts Visitors", default=True,
        help="Include this door's crossings in the store's visitor total. "
             "Turn it off for a staff-only or emergency door whose traffic is "
             "not customers — it stays measured, it just stops distorting the "
             "conversion rate.")
    device_ids = fields.One2many("analitix.device", "door_id", string="Devices")
    device_count = fields.Integer(compute="_compute_device_count")
    visitors_today = fields.Integer(
        compute="_compute_visitors_today", compute_sudo=True,
        string="Visitors Today")
    note = fields.Text(string="Notes")

    _code_store_uniq = models.Constraint(
        "unique(code, store_id)",
        "Another door of this store already uses that reference.")

    @api.depends("device_ids")
    def _compute_device_count(self):
        for door in self:
            door.device_count = len(door.device_ids)

    # Split from the count above rather than sharing one method: this one has
    # to run sudo (a salesperson may read their door's traffic without being
    # granted read on the raw event log), and Odoo requires every field of a
    # compute method to agree on compute_sudo.
    @api.depends("device_ids")
    def _compute_visitors_today(self):
        Event = self.env["analitix.event"]
        # Visitors so far in the selected period. The window is the *store's*
        # own day, so doors are grouped by store: two stores in different
        # timezones must not share one boundary.
        counts = {}
        for store in self.mapped("store_id"):
            doors = self.filtered(lambda d: d.store_id == store)
            start, end = store._period_window()
            domain = [
                ("door_id", "in", doors.ids), ("direction", "=", "in"),
                ("counted", "=", True), ("event_time", ">=", start),
            ]
            if end:
                domain.append(("event_time", "<", end))
            for door, total in Event._read_group(
                    domain, groupby=["door_id"], aggregates=["count:sum"]):
                counts[door.id] = total or 0
        for door in self:
            door.visitors_today = counts.get(door.id, 0)

    @api.depends("name", "store_id.name")
    def _compute_display_name(self):
        for door in self:
            door.display_name = (
                "%s / %s" % (door.store_id.name, door.name)
                if door.store_id else door.name)

    def action_view_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Crossing Events"),
            "res_model": "analitix.event",
            "view_mode": "list,graph,pivot,form",
            "domain": [("door_id", "=", self.id)],
            "context": {"default_door_id": self.id},
        }
