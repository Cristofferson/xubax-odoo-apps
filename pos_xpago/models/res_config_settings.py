from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_xpago_show_account = fields.Boolean(related='pos_config_id.xpago_show_account', readonly=False)
    pos_xpago_split = fields.Boolean(related='pos_config_id.xpago_split', readonly=False)
    pos_xpago_voucher_on_receipt = fields.Boolean(related='pos_config_id.xpago_voucher_on_receipt', readonly=False)
    pos_xpago_voucher_merchant = fields.Char(related='pos_config_id.xpago_voucher_merchant', readonly=False)
    pos_xpago_voucher_credit_text = fields.Text(related='pos_config_id.xpago_voucher_credit_text', readonly=False)
    pos_xpago_voucher_debit_text = fields.Text(related='pos_config_id.xpago_voucher_debit_text', readonly=False)
    pos_xpago_voucher_signature = fields.Boolean(related='pos_config_id.xpago_voucher_signature', readonly=False)
