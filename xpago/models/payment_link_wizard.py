from odoo import models
from odoo.http import request
from odoo.tools import float_repr
from odoo.tools.misc import hmac as hmac_tool


class PaymentLinkWizard(models.TransientModel):
    _inherit = 'payment.link.wizard'

    def _get_access_token(self):
        """Odoo signs the payment link with the database secret, read through the web request: an invoice PDF made
        outside one (sent by email in the background, a scheduled action) could not carry its pay link. Same values
        and same signature as Odoo's, from the environment."""
        if request:
            return super()._get_access_token()
        self.ensure_one()
        values = (self.partner_id.id, float(float_repr(self.amount, self.currency_id.decimal_places)),
                  self.currency_id.id)
        return hmac_tool(self.env(su=True), 'generate_access_token', '|'.join(str(value) for value in values))
