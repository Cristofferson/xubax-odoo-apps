from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_xb_jewelry_enabled = fields.Boolean(
        related="pos_config_id.xb_jewelry_enabled", readonly=False
    )
