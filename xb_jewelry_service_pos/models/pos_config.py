from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    xb_jewelry_enabled = fields.Boolean(
        string="Jewelry workshop",
        help="Show the jewelry button so this register can receive, look up "
        "and deliver repair pieces.",
    )
