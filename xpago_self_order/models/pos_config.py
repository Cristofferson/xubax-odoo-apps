from odoo import models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _load_pos_self_data_fields(self, pos_config_id):
        # The card voucher of the XPago terminal in the ticket the kiosk prints.
        return super()._load_pos_self_data_fields(pos_config_id) + [
            'xpago_voucher_on_receipt', 'xpago_voucher_merchant', 'xpago_voucher_credit_text',
            'xpago_voucher_debit_text', 'xpago_voucher_signature']
