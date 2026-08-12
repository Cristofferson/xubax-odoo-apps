# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Fields prefixed with `pos_` and related to pos_config_id are written back
    # to the Point of Sale selected on the settings page: the standard way of
    # surfacing a pos.config option there.
    pos_xb_bg_image = fields.Image(
        related="pos_config_id.xb_bg_image", readonly=False
    )
    pos_xb_bg_image_name = fields.Char(
        related="pos_config_id.xb_bg_image_name", readonly=False
    )
    pos_xb_bg_color = fields.Char(
        related="pos_config_id.xb_bg_color", readonly=False
    )
    pos_xb_bg_fit = fields.Selection(
        related="pos_config_id.xb_bg_fit", readonly=False
    )
    pos_xb_bg_darkening = fields.Integer(
        related="pos_config_id.xb_bg_darkening", readonly=False
    )
    pos_xb_bg_text = fields.Selection(
        related="pos_config_id.xb_bg_text", readonly=False
    )
    pos_xb_logo_source = fields.Selection(
        related="pos_config_id.xb_logo_source", readonly=False
    )
    pos_xb_logo = fields.Image(
        related="pos_config_id.xb_logo", readonly=False
    )
    pos_xb_logo_name = fields.Char(
        related="pos_config_id.xb_logo_name", readonly=False
    )
