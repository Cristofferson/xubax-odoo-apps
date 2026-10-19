# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_xb_va_auto_wall = fields.Boolean(related="pos_config_id.xb_va_auto_wall", readonly=False)
    pos_xb_va_follow_wall = fields.Boolean(related="pos_config_id.xb_va_follow_wall", readonly=False)
