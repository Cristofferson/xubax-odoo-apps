# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTag(models.Model):
    _inherit = 'product.tag'

    filter_group_id = fields.Many2one(
        'product.tag.group', string='Filter Group', ondelete='set null', index='btree_not_null',
        help='Shows this tag under its own title in the shop filters. Tags of the same group are '
             'combined with OR; different groups are combined with AND. Tags without a group stay '
             'in the standard "Tags" block.')

    def _xb_filter_buckets(self):
        """Split the tags shown in the shop into filter blocks.

        :return: list of ``(key, group, tags)``. The first block holds the tags without a group
            (``group`` is an empty recordset, rendered with Odoo's standard "Tags" title); then
            one block per group, in the group order.
        """
        buckets = []
        ungrouped = self.filtered(lambda t: not t.filter_group_id)
        if ungrouped:
            buckets.append(('tags', self.env['product.tag.group'], ungrouped))
        for group in self.filter_group_id.sorted():
            buckets.append(('tag_group_%s' % group.id, group,
                            self.filtered(lambda t, g=group: t.filter_group_id == g)))
        return buckets
