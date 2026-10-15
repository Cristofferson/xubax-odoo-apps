# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_xb_rawbt = fields.Boolean(related="pos_config_id.xb_rawbt", readonly=False)
    pos_xb_rawbt_paper = fields.Selection(related="pos_config_id.xb_rawbt_paper", readonly=False)
    pos_xb_rawbt_method = fields.Selection(related="pos_config_id.xb_rawbt_method", readonly=False)
    pos_xb_rawbt_format = fields.Selection(related="pos_config_id.xb_rawbt_format", readonly=False)
    pos_xb_rawbt_test_url = fields.Char(related="pos_config_id.xb_rawbt_test_url")
