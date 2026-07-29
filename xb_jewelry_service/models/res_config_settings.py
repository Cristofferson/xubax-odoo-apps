from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    xb_metal_attribute_id = fields.Many2one(
        related="company_id.xb_metal_attribute_id", readonly=False
    )
    xb_size_attribute_id = fields.Many2one(
        related="company_id.xb_size_attribute_id", readonly=False
    )
    xb_intake_photo_policy = fields.Selection(
        related="company_id.xb_intake_photo_policy", readonly=False
    )
    xb_intake_main_photo_kind_id = fields.Many2one(
        related="company_id.xb_intake_main_photo_kind_id", readonly=False
    )
    xb_scrap_tolerance = fields.Float(
        related="company_id.xb_scrap_tolerance", readonly=False
    )
    xb_warranty_days = fields.Integer(
        related="company_id.xb_warranty_days", readonly=False
    )
    xb_require_intake_signature = fields.Boolean(
        related="company_id.xb_require_intake_signature", readonly=False
    )
    xb_require_dispatch_signature = fields.Boolean(
        related="company_id.xb_require_dispatch_signature", readonly=False
    )
    xb_require_delivery_signature = fields.Boolean(
        related="company_id.xb_require_delivery_signature", readonly=False
    )
    xb_delivery_balance_policy = fields.Selection(
        related="company_id.xb_delivery_balance_policy", readonly=False
    )
    xb_custody_location_id = fields.Many2one(
        related="company_id.xb_custody_location_id", readonly=False
    )
    xb_custody_product_id = fields.Many2one(
        related="company_id.xb_custody_product_id", readonly=False
    )
    xb_jeweler_service_product_id = fields.Many2one(
        related="company_id.xb_jeweler_service_product_id", readonly=False
    )
    xb_photo_link_minutes = fields.Integer(
        related="company_id.xb_photo_link_minutes", readonly=False
    )
    xb_intake_terms = fields.Html(
        related="company_id.xb_intake_terms", readonly=False
    )
    xb_delivery_terms = fields.Html(
        related="company_id.xb_delivery_terms", readonly=False
    )
    xb_unclaimed_days = fields.Integer(
        related="company_id.xb_unclaimed_days", readonly=False
    )
