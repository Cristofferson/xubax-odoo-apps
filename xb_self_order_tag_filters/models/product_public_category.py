# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductPublicCategory(models.Model):
    _inherit = 'product.public.category'

    xb_kiosk_filter_title = fields.Char(
        string='Kiosk Filter Title', translate=True,
        help='When set, the subcategories of this category are offered as a filter in the '
             'self-order kiosk, under this title (e.g. "Metal").')
    xb_kiosk_filter_multi = fields.Boolean(
        string='Kiosk: Several at Once',
        help='The customer can pick several subcategories of this filter at once. Off: one at '
             'a time (e.g. a single metal).')
