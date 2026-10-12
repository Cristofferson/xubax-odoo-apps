# -*- coding: utf-8 -*-
from odoo import api, models

# Odoo's default tag color: not chosen by anyone, so not shown as a color dot.
DEFAULT_TAG_COLOR = '#3C3C3C'


class ProductTag(models.Model):
    _inherit = 'product.tag'

    @api.model
    def _load_pos_self_data_read(self, records, config):
        """Each tag carries its filter group, so the kiosk can build one block per group."""
        res = super()._load_pos_self_data_read(records, config)
        tags = {t.id: t for t in self.browse([r['id'] for r in res]).sudo()}
        for r in res:
            tag = tags.get(r['id'])
            group = tag.filter_group_id if tag else False
            r['_xb_seq'] = tag.sequence if tag else 0
            r['_xb_color'] = (tag and tag.color and tag.color.upper() != DEFAULT_TAG_COLOR
                              and tag.color) or False
            r['_xb_group'] = group and {
                'id': group.id, 'name': group.name, 'sequence': group.sequence,
                'single': group.xb_kiosk_single}
        return res
