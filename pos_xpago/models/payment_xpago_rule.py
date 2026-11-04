from odoo import fields, models


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
