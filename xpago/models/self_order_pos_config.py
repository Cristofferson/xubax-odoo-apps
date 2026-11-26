from odoo import api, fields, models


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

    @api.model
    def _load_pos_self_data_fields(self, config_id):
        # The kiosk prints the card voucher in its ticket too.
        return super()._load_pos_self_data_fields(config_id) + [
            'xpago_voucher_on_receipt', 'xpago_voucher_merchant', 'xpago_voucher_credit_text',
            'xpago_voucher_debit_text', 'xpago_voucher_signature', 'xpago_kiosk_timeout',
            'xpago_kiosk_transfer_timeout',
        ]
