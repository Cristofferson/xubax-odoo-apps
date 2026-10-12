# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTagGroup(models.Model):
    _inherit = 'product.tag.group'

    xb_kiosk_single = fields.Boolean(
        string='Kiosk: One at a Time',
        help='In the self-order kiosk the customer picks a single tag of this group. Off: '
             'several at once, products with any of them are shown.')
