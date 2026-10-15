# -*- coding: utf-8 -*-
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        # The kiosk only gets the translations of the modules listed here.
        return super()._get_translation_frontend_modules_name() + ["analitix_self_order"]
