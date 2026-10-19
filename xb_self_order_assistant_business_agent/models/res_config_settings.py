# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_xb_va_ba_kb_source = fields.Selection(related="pos_config_id.xb_va_ba_kb_source", readonly=False)
    pos_xb_va_ba_account_id = fields.Many2one(related="pos_config_id.xb_va_ba_account_id", readonly=False)
