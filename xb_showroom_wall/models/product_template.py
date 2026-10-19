# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # The shop decides piece by piece what goes on the wall: a counter full of
    # earrings and gift boxes is published too, and a sales person tapping
    # "show on wall" on one of those puts a half-empty layout in front of the
    # customer.
    xb_showroom_enabled = fields.Boolean(
        string='Show on the showroom wall', copy=True,
        help="Sales people get the 'Show on wall' and 'Compare' buttons for "
             "this product on the website, and it may rotate in the wall's "
             "shop window.")
