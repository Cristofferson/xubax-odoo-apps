from odoo import models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _get_allowed_payment_methods(self):
        """The kiosk also offers the XPago terminals of this point of sale."""
        methods = super()._get_allowed_payment_methods()
        if self.self_ordering_mode == 'kiosk':
            methods |= self.payment_method_ids.filtered(lambda m: m.use_payment_terminal == 'xpago')
        return methods
