from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    # A customer who walks away from the kiosk must not leave the terminal waiting for a card the next one cannot use.
    xpago_kiosk_timeout = fields.Integer(
        string="Cancel an unpaid card charge after (seconds)", default=120,
        help="When nobody pays on the XPago terminal of the kiosk within this time, the charge is cancelled and the "
             "terminal is free for the next customer. 0 never cancels it.",
    )

    # A transfer takes longer than a card: the customer opens the bank's app, copies the CLABE and sends the money.
    xpago_kiosk_transfer_timeout = fields.Integer(
        string="Cancel an unpaid kiosk transfer after (seconds)", default=600,
        help="When the money of an XPago transfer does not arrive within this time, the kiosk cancels the CLABE and "
             "goes back to the start. 0 never cancels it.",
    )

    def _get_allowed_payment_methods(self):
        """The kiosk also offers the XPago terminals and the XPago transfer of this point of sale."""
        methods = super()._get_allowed_payment_methods()
        if self.self_ordering_mode == 'kiosk':
            methods |= self.payment_method_ids.filtered(lambda m: m.use_payment_terminal in ('xpago', 'xpago_spei'))
        return methods

    def _get_self_ordering_data(self):
        """The kiosk frees the XPago terminal and cancels the unpaid CLABE after its own timeouts."""
        data = super()._get_self_ordering_data()
        data['config']['xpago_kiosk_timeout'] = self.xpago_kiosk_timeout
        data['config']['xpago_kiosk_transfer_timeout'] = self.xpago_kiosk_transfer_timeout
        return data
