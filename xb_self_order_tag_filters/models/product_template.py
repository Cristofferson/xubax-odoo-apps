# -*- coding: utf-8 -*-
from odoo import models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _load_pos_self_data_read(self, data, config):
        """Each product carries the website sections it belongs to that are kiosk filters:
        the subcategories of a category with a kiosk filter title."""
        res = super()._load_pos_self_data_read(data, config)
        ids = [r['id'] for r in res]
        if not ids:
            return res
        Category = self.env['product.public.category'].sudo()
        parents = Category.search([('xb_kiosk_filter_title', '!=', False)])
        sections = {}
        if parents:
            for tmpl in self.sudo().browse(ids):
                for categ in tmpl.public_categ_ids.filtered(lambda c: c.parent_id in parents):
                    sections.setdefault(tmpl.id, []).append({
                        'group': {'id': 'c%s' % categ.parent_id.id,
                                  'name': categ.parent_id.xb_kiosk_filter_title,
                                  'sequence': categ.parent_id.sequence,
                                  'single': not categ.parent_id.xb_kiosk_filter_multi},
                        'id': 'c%s' % categ.id, 'name': categ.name, 'sequence': categ.sequence,
                    })
        for r in res:
            r['_xb_sections'] = sections.get(r['id'], [])
        return res
