from odoo import api, models


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    @api.model
    def _get_xml_ids_to_load(self):
        # The CLABE slip of an XPago transfer, printed by the point of sale.
        return super()._get_xml_ids_to_load() + ['xpago.pos_clabe_receipt']
