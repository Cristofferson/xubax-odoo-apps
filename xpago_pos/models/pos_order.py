from odoo import models

from .pos_payment import XPAGO_CARD_FIELDS


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _payment_fields(self, order, ui_paymentline):
        result = super()._payment_fields(order, ui_paymentline)
        result.update({name: ui_paymentline[name] for name in XPAGO_CARD_FIELDS if ui_paymentline.get(name)})
        return result
