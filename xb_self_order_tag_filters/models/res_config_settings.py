# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_xb_tf_layout = fields.Selection(related='pos_config_id.xb_tf_layout', readonly=False)
    pos_xb_tf_icons = fields.Selection(related='pos_config_id.xb_tf_icons', readonly=False)
    pos_xb_tf_show_count = fields.Boolean(related='pos_config_id.xb_tf_show_count', readonly=False)
    pos_xb_tf_categ_ids = fields.Many2many(related='pos_config_id.xb_tf_categ_ids', readonly=False)
    pos_xb_tf_color_ink = fields.Char(related='pos_config_id.xb_tf_color_ink', readonly=False)
    pos_xb_tf_color_accent = fields.Char(related='pos_config_id.xb_tf_color_accent', readonly=False)
