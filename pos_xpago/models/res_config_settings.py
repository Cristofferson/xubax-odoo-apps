from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_xpago_show_account = fields.Boolean(related='pos_config_id.xpago_show_account', readonly=False)
    pos_xpago_split = fields.Boolean(related='pos_config_id.xpago_split', readonly=False)
