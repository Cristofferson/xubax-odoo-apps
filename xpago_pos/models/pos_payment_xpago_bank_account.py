from odoo import models


class PaymentXpagoBankAccount(models.Model):
    _inherit = 'payment.xpago.bank.account'

    def _xpago_pos_accounts(self, config):
        """The active deposit accounts of the XPago accounts the terminals of this point of sale charge with."""
        providers = config.payment_method_ids.filtered(lambda m: m.use_payment_terminal == 'xpago').xpago_provider_id
        return self.search([('provider_id', 'in', providers.ids), ('active', '=', True)])
