# -*- coding: utf-8 -*-
from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def _load_pos_self_data_fields(self, config):
        return super()._load_pos_self_data_fields(config) + ['xb_showroom_enabled']
