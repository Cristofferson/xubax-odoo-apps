from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        # The self-order kiosk only loads the translations of the modules named here: without XPago, its words on
        # the kiosk (the CLABE screen, the card timeout) stay in English.
        return super()._get_translation_frontend_modules_name() + ['xpago']
