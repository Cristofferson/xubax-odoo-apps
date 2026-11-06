from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_xpago_kiosk_timeout = fields.Integer(related='pos_config_id.xpago_kiosk_timeout', readonly=False)
