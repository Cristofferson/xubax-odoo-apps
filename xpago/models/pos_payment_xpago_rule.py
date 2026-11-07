from odoo import api, fields, models


class PaymentXpagoRule(models.Model):
    _inherit = 'payment.xpago.rule'

    use_pos = fields.Boolean(string="Point of sale", default=True)
    use_kiosk = fields.Boolean(string="Kiosk", default=True)
    config_ids = fields.Many2many('pos.config', string="Only these points of sale",
                                  help="Empty: every point of sale and kiosk.")

    def _xpago_fits_channel(self, channel, config):
        if channel not in ('pos', 'kiosk'):
            return super()._xpago_fits_channel(channel, config)
        self.ensure_one()
        if not (self.use_pos if channel == 'pos' else self.use_kiosk):
            return False
        return not self.config_ids or bool(config and config in self.config_ids)

    @api.model
    def _xpago_skip_line(self, line, config):
        """A tip is not a product sold: it goes with the rest of the sale."""
        tip = config.tip_product_id if config and 'tip_product_id' in config._fields else None
        return super()._xpago_skip_line(line, config) or bool(tip and line.get('product') == tip)
