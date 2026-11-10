# -*- coding: utf-8 -*-
"""Odoo 17 register loading.

Odoo 17 has no ``pos.load.mixin``: the register asks the session for each
model through a ``_loader_params_<model>`` / ``_get_pos_ui_<model>`` pair. The
domains and field lists stay on the models (``_load_pos_data_domain`` /
``_load_pos_data_fields``, the same methods 18+ uses), so this file only wires
them in. Everything but the account is limited to the account this register
is served by.
"""
from odoo import models

from .pos_compat import pos_config_record

TAECEL_MODELS = [
    'xb.taecel.account',
    'xb.taecel.wallet',
    'xb.taecel.carrier',
    'xb.taecel.product',
    'xb.taecel.transaction',
]


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _pos_ui_models_to_load(self):
        return super()._pos_ui_models_to_load() + TAECEL_MODELS

    def _xb_taecel_params(self, model):
        Model = self.env[model]
        config = pos_config_record(self.env, self.config_id)
        domain = list(Model._load_pos_data_domain({}, config))
        if model != 'xb.taecel.account':
            accounts = self.env['xb.taecel.account'].search(
                self.env['xb.taecel.account']._load_pos_data_domain({}, config))
            if model == 'xb.taecel.transaction':
                domain += [('account_id', 'in', accounts.ids), ('pos_session_id', '=', self.id)]
            else:
                domain += [('account_id', 'in', accounts.ids)]
        return {'search_params': {'domain': domain, 'fields': Model._load_pos_data_fields(config)}}

    def _xb_taecel_read(self, model, params):
        return self.env[model].search_read(**params['search_params'])

    def _loader_params_xb_taecel_account(self):
        return self._xb_taecel_params('xb.taecel.account')

    def _get_pos_ui_xb_taecel_account(self, params):
        return self._xb_taecel_read('xb.taecel.account', params)

    def _loader_params_xb_taecel_wallet(self):
        return self._xb_taecel_params('xb.taecel.wallet')

    def _get_pos_ui_xb_taecel_wallet(self, params):
        return self._xb_taecel_read('xb.taecel.wallet', params)

    def _loader_params_xb_taecel_carrier(self):
        return self._xb_taecel_params('xb.taecel.carrier')

    def _get_pos_ui_xb_taecel_carrier(self, params):
        return self._xb_taecel_read('xb.taecel.carrier', params)

    def _loader_params_xb_taecel_product(self):
        return self._xb_taecel_params('xb.taecel.product')

    def _get_pos_ui_xb_taecel_product(self, params):
        return self._xb_taecel_read('xb.taecel.product', params)

    def _loader_params_xb_taecel_transaction(self):
        return self._xb_taecel_params('xb.taecel.transaction')

    def _get_pos_ui_xb_taecel_transaction(self, params):
        return self._xb_taecel_read('xb.taecel.transaction', params)
