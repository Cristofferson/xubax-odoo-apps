# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_xb_bq_enabled = fields.Boolean(related="pos_config_id.xb_bq_enabled", readonly=False)
    pos_xb_bq_color_primary = fields.Char(related="pos_config_id.xb_bq_color_primary", readonly=False)
    pos_xb_bq_color_ink = fields.Char(related="pos_config_id.xb_bq_color_ink", readonly=False)
    pos_xb_bq_color_photo = fields.Char(related="pos_config_id.xb_bq_color_photo", readonly=False)
    pos_xb_bq_color_line = fields.Char(related="pos_config_id.xb_bq_color_line", readonly=False)
    pos_xb_bq_font_title = fields.Selection(related="pos_config_id.xb_bq_font_title", readonly=False)
    pos_xb_bq_font_body = fields.Selection(related="pos_config_id.xb_bq_font_body", readonly=False)
    pos_xb_bq_corners = fields.Selection(related="pos_config_id.xb_bq_corners", readonly=False)
    pos_xb_bq_columns = fields.Selection(related="pos_config_id.xb_bq_columns", readonly=False)
    pos_xb_bq_price = fields.Selection(related="pos_config_id.xb_bq_price", readonly=False)
    pos_xb_bq_gallery = fields.Selection(related="pos_config_id.xb_bq_gallery", readonly=False)
    pos_xb_bq_txt_checkout = fields.Char(related="pos_config_id.xb_bq_txt_checkout", readonly=False)
    pos_xb_bq_txt_order = fields.Char(related="pos_config_id.xb_bq_txt_order", readonly=False)
    pos_xb_bq_txt_cart_title = fields.Char(related="pos_config_id.xb_bq_txt_cart_title", readonly=False)
    pos_xb_bq_txt_done = fields.Char(related="pos_config_id.xb_bq_txt_done", readonly=False)
    pos_xb_bq_txt_number = fields.Char(related="pos_config_id.xb_bq_txt_number", readonly=False)
    pos_xb_bq_txt_from = fields.Char(related="pos_config_id.xb_bq_txt_from", readonly=False)
    pos_xb_bq_app = fields.Boolean(related="pos_config_id.xb_bq_app", readonly=False)
    pos_xb_bq_app_name = fields.Char(related="pos_config_id.xb_bq_app_name", readonly=False)
    pos_xb_bq_app_icon = fields.Image(related="pos_config_id.xb_bq_app_icon", readonly=False)
    pos_xb_bq_bar_color = fields.Char(related="pos_config_id.xb_bq_bar_color", readonly=False)
