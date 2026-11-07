from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _pos_ui_models_to_load(self):
        return super()._pos_ui_models_to_load() + ['payment.xpago.bank.account']

    def _loader_params_payment_xpago_bank_account(self):
        return {'search_params': {'fields': ['id', 'name', 'is_default', 'sequence']}}

    def _get_pos_ui_payment_xpago_bank_account(self, params):
        accounts = self.env['payment.xpago.bank.account'].sudo()._xpago_pos_accounts(self.config_id)
        return accounts.read(params['search_params']['fields'])

    def _loader_params_pos_payment_method(self):
        result = super()._loader_params_pos_payment_method()
        result['search_params']['fields'] += ['xpago_open_terminal_app', 'xpago_choose_account', 'xpago_bank_account_id']
        return result
