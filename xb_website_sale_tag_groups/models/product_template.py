# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.fields import Domain


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def _search_get_detail(self, website, order, options):
        """Tags of the same filter group are combined with OR, different groups with AND.

        Odoo combines every selected tag with OR, so ticking "Eternity" (style) and "Solitaire"
        (stones) would show products that have *either* tag. Here the grouped tags are taken out
        of the standard option and each group becomes its own condition, like attributes do.
        """
        tags = options.get('tags')
        if not tags:
            return super()._search_get_detail(website, order, options)
        if isinstance(tags, str):
            tags = tags.split(',')
        unslug = self.env['ir.http']._unslug
        tag_ids = [i for i in (unslug(str(t).strip())[1] for t in tags) if i]
        selected = self.env['product.tag'].sudo().browse(tag_ids).exists()
        grouped = selected.filtered('filter_group_id')
        if not grouped:
            return super()._search_get_detail(website, order, options)
        ungrouped = selected - grouped
        options = dict(options, tags=','.join(map(str, ungrouped.ids)) or None)
        detail = super()._search_get_detail(website, order, options)
        for group in grouped.filter_group_id:
            ids = grouped.filtered(lambda t, g=group: t.filter_group_id == g).ids
            detail['base_domain'].append(Domain.OR([
                Domain('product_tag_ids', 'in', ids),
                Domain('product_variant_ids.additional_product_tag_ids', 'in', ids),
            ]))
        return detail
