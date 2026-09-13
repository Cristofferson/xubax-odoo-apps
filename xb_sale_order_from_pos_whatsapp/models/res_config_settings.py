# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_xb_quotation_wa_template_id = fields.Many2one(
        related="pos_config_id.xb_quotation_wa_template_id", readonly=False
    )
    xb_ready_wa_template_id = fields.Many2one(
        related="company_id.xb_ready_wa_template_id", readonly=False
    )
