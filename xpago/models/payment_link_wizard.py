from odoo import models
from odoo.http import request
from odoo.tools.misc import hmac as hmac_tool


class PaymentLinkWizard(models.TransientModel):
    _inherit = 'payment.link.wizard'

    def _prepare_access_token(self):
        """Odoo signs the payment link with the database secret, read through the web request: an invoice PDF made
        outside one (sent by email in the background, a scheduled action) could not carry its pay link. Same values
        and same signature as Odoo's, from the environment."""
        if request:
            return super()._prepare_access_token()
        self.ensure_one()
        if self.res_model == 'account.move':
            values = (self.res_id, self.amount)
        else:
            values = (self.partner_id.id, self.amount, self.currency_id.id)
        return hmac_tool(self.env(su=True), 'generate_access_token', '|'.join(str(value) for value in values))
