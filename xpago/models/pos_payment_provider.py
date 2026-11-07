from odoo import api, models


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    @api.model
    def _xpago_providers_to_connect(self, company=None):
        """Also the XPago account of a terminal of the point of sale, even while its provider is disabled online."""
        providers = super()._xpago_providers_to_connect(company)
        company = company or self.env.company
        terminals = self.env['pos.payment.method'].sudo().search([
            ('payment_provider', '=', 'xpago'), ('company_id', 'in', company.parent_ids.ids)])
        return providers | terminals.xpago_provider_id.filtered('xpago_needs_connect')
