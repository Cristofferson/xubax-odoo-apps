from odoo import fields, models


class PaymentXpagoConnection(models.Model):
    """How the last calls to XPago went, for the connection panel of the provider. Kept apart from the provider so
    writing it never holds the provider's record while a cashier charges."""
    _name = 'payment.xpago.connection'
    _description = "XPago connection status"

    provider_id = fields.Many2one('payment.provider', required=True, index=True, ondelete='cascade')
    last_ok_at = fields.Datetime(string="Last call that worked", readonly=True)
    last_error_at = fields.Datetime(string="Last error", readonly=True)
    last_error = fields.Char(string="Error", readonly=True)
    account_name = fields.Char(string="XPago account", readonly=True)

    _sql_constraints = [('provider_unique', 'UNIQUE(provider_id)', "One connection status per provider.")]
