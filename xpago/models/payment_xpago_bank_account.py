from odoo import _, fields, models


class PaymentXpagoBankAccount(models.Model):
    """A bank account XPago deposits in, as XPago lists it. Accounts are added and removed in XPago only."""
    _name = 'payment.xpago.bank.account'
    _description = "XPago deposit account"
    _order = 'sequence, id'

    provider_id = fields.Many2one('payment.provider', required=True, ondelete='cascade', index=True)
    xpago_id = fields.Char(string="XPago id", required=True, readonly=True)
    name = fields.Char(required=True, readonly=True)
    is_default = fields.Boolean(string="XPago default", readonly=True,
                                help="Where XPago deposits a sale that names no account.")
    sequence = fields.Integer(readonly=True)
    active = fields.Boolean(default=True, readonly=True)

    _xpago_id_unique = models.Constraint('unique(provider_id, xpago_id)', "This XPago account already exists.")

    def _compute_display_name(self):
        for account in self:
            account.display_name = f"{account.name} ({_('XPago default')})" if account.is_default else account.name
