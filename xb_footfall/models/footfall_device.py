# -*- coding: utf-8 -*-
import secrets

from odoo import api, fields, models, _


class FootfallDevice(models.Model):
    _name = "xb.footfall.device"
    _description = "Footfall Counting Device"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    device_uid = fields.Char(
        string="Device UID", required=True, copy=False, index=True,
        help="Stable identifier sent by the sensor/edge in every payload "
             "(e.g. 'anello-morelia-puerta1').")
    company_id = fields.Many2one(
        "res.company", string="Store / Company", required=True,
        default=lambda self: self.env.company,
        help="Company that represents the physical store. POS orders of this "
             "company are cross-referenced to compute conversion.")
    pos_config_id = fields.Many2one(
        "pos.config", string="POS Register / Store",
        help="Specific POS register this door belongs to. Set this when several "
             "stores share one company (e.g. multiple shops under the same "
             "legal entity): conversion is then crossed against THIS register's "
             "orders only. Leave empty if the company has a single store.")
    kind = fields.Selection(
        selection=[
            ("cctv_hik", "CCTV — Hikvision (ISAPI People Counting)"),
            ("cctv_dahua", "CCTV — Dahua"),
            ("diy_cv", "DIY edge (YOLO + ByteTrack)"),
            ("ir_beam", "IR beam counter"),
            ("other", "Other"),
        ],
        string="Sensor Type", default="diy_cv", required=True)
    access_token = fields.Char(
        string="Access Token", copy=False, index=True,
        groups="base.group_system",
        help="Bearer token the device uses to authenticate against the ingest "
             "endpoint. Keep it secret; regenerate if leaked.")
    active = fields.Boolean(default=True)
    last_seen = fields.Datetime(string="Last Seen", readonly=True, copy=False)
    event_count = fields.Integer(
        string="Events", compute="_compute_event_count")
    note = fields.Text(string="Notes")

    _sql_constraints = [
        ("device_uid_uniq", "unique(device_uid)",
         "The Device UID must be unique."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("access_token"):
                vals["access_token"] = secrets.token_urlsafe(32)
        return super().create(vals_list)

    def _compute_event_count(self):
        data = self.env["xb.footfall.event"]._read_group(
            [("device_id", "in", self.ids)],
            groupby=["device_id"], aggregates=["__count"])
        mapped = {dev.id: count for dev, count in data}
        for device in self:
            device.event_count = mapped.get(device.id, 0)

    def action_regenerate_token(self):
        """Generate a fresh token and reveal it once via a notification."""
        self.ensure_one()
        token = secrets.token_urlsafe(32)
        self.sudo().access_token = token
        self.message_post(body=_("Access token regenerated."))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("New access token (shown once)"),
                "message": token,
                "type": "warning",
                "sticky": True,
            },
        }

    def action_view_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Crossing Events"),
            "res_model": "xb.footfall.event",
            "view_mode": "list,graph,pivot,form",
            "domain": [("device_id", "=", self.id)],
            "context": {"default_device_id": self.id},
        }
