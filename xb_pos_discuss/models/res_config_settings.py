# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Related field bound to the Point of Sale selected in the settings page,
    # the standard way of surfacing a pos.config option there.
    pos_xb_discuss_enabled = fields.Boolean(
        related="pos_config_id.xb_discuss_enabled", readonly=False
    )
