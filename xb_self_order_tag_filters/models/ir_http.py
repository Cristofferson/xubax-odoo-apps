# -*- coding: utf-8 -*-
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        # The kiosk only loads the translations of the modules listed here.
        return super()._get_translation_frontend_modules_name() + ['xb_self_order_tag_filters']
