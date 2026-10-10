# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_xb_kiosk_quotation = fields.Boolean(related="pos_config_id.xb_kiosk_quotation", readonly=False)
    pos_xb_kiosk_counter_order = fields.Boolean(related="pos_config_id.xb_kiosk_counter_order", readonly=False)
    pos_xb_kiosk_privacy_url = fields.Char(related="pos_config_id.xb_kiosk_privacy_url", readonly=False)
