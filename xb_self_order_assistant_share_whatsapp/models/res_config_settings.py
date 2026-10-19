# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_xb_va_wa_send_template_id = fields.Many2one(related="pos_config_id.xb_va_wa_send_template_id", readonly=False)
    pos_xb_va_create_lead = fields.Boolean(related="pos_config_id.xb_va_create_lead", readonly=False)

    def action_xb_va_create_wa_template(self):
        self.ensure_one()
        return self.pos_config_id.action_xb_va_create_wa_template()
