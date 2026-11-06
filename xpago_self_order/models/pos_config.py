from odoo import api, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.model
    def _load_pos_self_data_fields(self, config_id):
        # The kiosk prints the card voucher in its ticket too.
        return super()._load_pos_self_data_fields(config_id) + [
            'xpago_voucher_on_receipt', 'xpago_voucher_merchant', 'xpago_voucher_credit_text',
            'xpago_voucher_debit_text', 'xpago_voucher_signature',
        ]
