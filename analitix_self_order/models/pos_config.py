# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    analitix_kiosk_camera = fields.Boolean(
        string="Measure the kiosk with its camera",
        help="The kiosk reads its front camera in the browser and sends Analitix "
             "one row per person who stops: time, use, approximate age and gender, "
             "and whether it ended in a sale. No image leaves the tablet.")
    analitix_store_id = fields.Many2one(
        "analitix.store", string="Analitix store",
        domain="[('company_id', '=', company_id)]")
    analitix_kiosk_min_face = fields.Integer(
        string="Closest distance (face size %)", default=12,
        help="Faces smaller than this share of the image width are people walking "
             "by in the back, not people at the kiosk. Raise it if the kiosk counts "
             "passers-by; lower it if it misses people standing in front.")
    analitix_kiosk_debug = fields.Boolean(
        string="Show the camera reading",
        help="A small box on the kiosk shows how many faces it sees, for setting it "
             "up. Turn it off for customers.")

    def _analitix_kiosk_data(self):
        self.ensure_one()
        if not (self.analitix_kiosk_camera and self.analitix_store_id
                and self.self_ordering_mode == "kiosk"):
            return False
        version = self.env["ir.module.module"].sudo().search(
            [("name", "=", "analitix_self_order")], limit=1).latest_version or ""
        base = "/analitix_self_order/static/lib/face-api/"
        return {
            "min_face": max(self.analitix_kiosk_min_face or 0, 1) / 100.0,
            "debug": bool(self.analitix_kiosk_debug),
            # The version in the URL: a tablet that kept an older copy loads this one.
            "lib": base + "face-api.js?v=" + version,
            "models": base + "model",
        }

    @api.model
    def _load_pos_self_data_read(self, records, config):
        read_records = super()._load_pos_self_data_read(records, config)
        if read_records:
            read_records[0]["_analitix_kiosk"] = config._analitix_kiosk_data()
        return read_records
