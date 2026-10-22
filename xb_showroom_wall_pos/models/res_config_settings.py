# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_xb_showroom_pos_screen_id = fields.Many2one(
        related='pos_config_id.xb_showroom_pos_screen_id', readonly=False)
