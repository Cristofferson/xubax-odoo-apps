# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductPublicCategory(models.Model):
    _inherit = 'product.public.category'

    xb_kiosk_filter_title = fields.Char(
        string='Kiosk Filter Title', translate=True,
        help='When set, the subcategories of this category are offered as a filter in the '
             'self-order kiosk, under this title (e.g. "Metal").')
