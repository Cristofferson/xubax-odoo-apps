# -*- coding: utf-8 -*-
from odoo import models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _get_special_products(self):
        """The generic recharge product is loaded by every register, like the tip product: a register that only
        shows some categories would otherwise not have it, and could not sell recharges or bill payments."""
        product = self.env.ref('xb_pos_taecel.product_taecel_service', raise_if_not_found=False)
        return super()._get_special_products() | (product.sudo().product_variant_id if product else self.env['product.product'])
