from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_price_checker_show_stock = fields.Boolean(related='pos_config_id.price_checker_show_stock', readonly=False)
    pos_price_checker_show_months = fields.Boolean(related='pos_config_id.price_checker_show_months', readonly=False)
    pos_price_checker_idle = fields.Integer(related='pos_config_id.price_checker_idle', readonly=False)
    pos_price_checker_url = fields.Char(related='pos_config_id.price_checker_url')

    def action_price_checker_open(self):
        return self.pos_config_id.action_price_checker_open()

    def action_price_checker_new_link(self):
        self.pos_config_id.action_price_checker_new_link()
