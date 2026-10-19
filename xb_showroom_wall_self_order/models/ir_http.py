# -*- coding: utf-8 -*-
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        # The kiosk only loads the translations of the modules listed here:
        # without it the wall button stays in English on a Spanish kiosk.
        mods = super()._get_translation_frontend_modules_name()
        return mods + ['xb_showroom_wall_self_order']
