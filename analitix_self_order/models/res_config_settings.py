# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_analitix_kiosk_camera = fields.Boolean(
        related="pos_config_id.analitix_kiosk_camera", readonly=False)
    pos_analitix_store_id = fields.Many2one(
        related="pos_config_id.analitix_store_id", readonly=False)
    pos_analitix_kiosk_min_face = fields.Integer(
        related="pos_config_id.analitix_kiosk_min_face", readonly=False)
    pos_analitix_kiosk_debug = fields.Boolean(
        related="pos_config_id.analitix_kiosk_debug", readonly=False)
