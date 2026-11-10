from odoo import api, models


class PaymentXpagoBankAccount(models.Model):
    _name = 'payment.xpago.bank.account'
    _inherit = ['payment.xpago.bank.account', 'pos.load.mixin']

    @api.model
    def _load_pos_data_domain(self, data):
        config = self.env['pos.config'].browse(data['pos.config'][0]['id'])
        providers = config.payment_method_ids.filtered(lambda m: m.use_payment_terminal == 'xpago').xpago_provider_id
        return [('provider_id', 'in', providers.ids), ('active', '=', True)]

    @api.model
    def _load_pos_data_fields(self, config_id):
        return ['id', 'name', 'is_default', 'sequence']
