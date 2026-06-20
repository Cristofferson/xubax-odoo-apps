# -*- coding: utf-8 -*-
from odoo import _, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def open_pricelist_rules(self):
        self.ensure_one()
        # Odoo 17 already counts/lists formula rules on the smart button. We
        # only swap the opened list for an informative one (computation, base,
        # discount, resulting price) instead of the standard list that forces a
        # required "Fixed Price" column on formula rules.
        domain = [
            "&",
            "|",
            ("product_tmpl_id", "=", self.id),
            ("product_id", "in", self.product_variant_ids.ids),
            ("pricelist_id.active", "=", True),
        ]
        return {
            "name": _("Pricelist Rules"),
            "view_mode": "tree,form",
            "views": [
                (
                    self.env.ref(
                        "xb_product_pricelist_rules."
                        "product_pricelist_item_tree_view_all"
                    ).id,
                    "tree",
                ),
                (False, "form"),
            ],
            "res_model": "product.pricelist.item",
            "type": "ir.actions.act_window",
            "target": "current",
            "domain": domain,
            "context": {
                "default_product_tmpl_id": self.id,
                "default_applied_on": "1_product",
                "product_without_variants": self.product_variant_count == 1,
                "search_default_visible": True,
            },
        }
