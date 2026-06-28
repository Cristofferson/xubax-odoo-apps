# -*- coding: utf-8 -*-
from odoo import fields, models


class FootfallEvent(models.Model):
    _name = "xb.footfall.event"
    _description = "Footfall Crossing Event"
    _order = "event_time desc, id desc"
    _rec_name = "event_time"

    device_id = fields.Many2one(
        "xb.footfall.device", string="Device", required=True,
        ondelete="cascade", index=True)
    company_id = fields.Many2one(
        related="device_id.company_id", string="Store / Company",
        store=True, index=True)
    event_time = fields.Datetime(
        string="Time", required=True, index=True,
        default=lambda self: fields.Datetime.now())
    direction = fields.Selection(
        selection=[("in", "Entrance"), ("out", "Exit")],
        string="Direction", required=True, default="in")
    count = fields.Integer(string="People", default=1)
    seq = fields.Integer(
        string="Device Sequence",
        help="Per-device monotonic sequence sent by the edge, used to drop "
             "duplicates on retries.")
