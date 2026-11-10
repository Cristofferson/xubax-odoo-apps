# -*- coding: utf-8 -*-
from odoo import api, models


class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def _load_pos_data_models(self, config):
        # ``config`` is positional: Odoo 18 passes the config id here, Odoo 19
        # the recordset. We only pass it through to super, so either binds.
        data = super()._load_pos_data_models(config)
        return data + [
            'xb.taecel.account',
            'xb.taecel.wallet',
            'xb.taecel.carrier',
            'xb.taecel.product',
            'xb.taecel.transaction',
        ]
