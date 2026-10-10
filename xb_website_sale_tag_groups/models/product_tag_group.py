# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTagGroup(models.Model):
    _name = 'product.tag.group'
    _description = 'Product Tag Filter Group'
    _order = 'sequence, id'

    name = fields.Char(
        string='Filter Title', required=True, translate=True,
        help='Title of this block in the shop filters, e.g. "Style" or "Stones".')
    sequence = fields.Integer(default=10)
    tag_ids = fields.One2many('product.tag', 'filter_group_id', string='Tags')
    tag_count = fields.Integer(compute='_compute_tag_count', string='Number of Tags')

    _name_uniq = models.Constraint('unique (name)', 'A filter group with this title already exists!')

    def _compute_tag_count(self):
        counts = dict(self.env['product.tag']._read_group(
            [('filter_group_id', 'in', self.ids)], ['filter_group_id'], ['__count']))
        for group in self:
            group.tag_count = counts.get(group, 0)
