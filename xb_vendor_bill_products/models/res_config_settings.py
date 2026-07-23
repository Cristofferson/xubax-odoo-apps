# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    xb_vbp_mode = fields.Selection(
        related='company_id.xb_vbp_mode', readonly=False)
    xb_vbp_categ_id = fields.Many2one(
        related='company_id.xb_vbp_categ_id', readonly=False)
    xb_vbp_product_type = fields.Selection(
        related='company_id.xb_vbp_product_type', readonly=False)
    xb_vbp_is_storable = fields.Boolean(
        related='company_id.xb_vbp_is_storable', readonly=False)
    xb_vbp_set_barcode = fields.Boolean(
        related='company_id.xb_vbp_set_barcode', readonly=False)
    xb_vbp_set_default_code = fields.Boolean(
        related='company_id.xb_vbp_set_default_code', readonly=False)

    xb_vbp_cost_policy = fields.Selection(
        related='company_id.xb_vbp_cost_policy', readonly=False)
    xb_vbp_update_standard_price = fields.Boolean(
        related='company_id.xb_vbp_update_standard_price', readonly=False)
    xb_vbp_margin_percent = fields.Float(
        related='company_id.xb_vbp_margin_percent', readonly=False)

    xb_vbp_image_mode = fields.Selection(
        related='company_id.xb_vbp_image_mode', readonly=False)
    xb_vbp_image_provider = fields.Selection(
        related='company_id.xb_vbp_image_provider', readonly=False)
    xb_vbp_image_google_key = fields.Char(
        related='company_id.xb_vbp_image_google_key', readonly=False)
    xb_vbp_image_google_cx = fields.Char(
        related='company_id.xb_vbp_image_google_cx', readonly=False)
    xb_vbp_image_candidates = fields.Integer(
        related='company_id.xb_vbp_image_candidates', readonly=False)
    xb_vbp_image_min_px = fields.Integer(
        related='company_id.xb_vbp_image_min_px', readonly=False)
    xb_vbp_image_query_suffix = fields.Char(
        related='company_id.xb_vbp_image_query_suffix', readonly=False)
