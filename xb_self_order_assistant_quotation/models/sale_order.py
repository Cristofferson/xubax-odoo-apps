# -*- coding: utf-8 -*-
from odoo import api, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def xb_create_order_from_pos(self, payload):
        result = super().xb_create_order_from_pos(payload)
        config = self.env["pos.config"].browse(payload.get("pos_config_id")).exists()
        if config.self_ordering_mode == "kiosk":
            order = self.browse(result.get("sale_order_id") if isinstance(result, dict) else False).exists()
            if order:
                self.env["xb.va.conversation"]._xb_va_link_sale(config, order.amount_total, order.name)
        return result
