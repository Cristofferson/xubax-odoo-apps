# -*- coding: utf-8 -*-
from odoo import _, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _compute_item_count(self):
        # Standard Odoo 18 restricts the count to rules with
        # compute_price='fixed', hiding formula/percentage rules. We count
        # every rule applicable to the template or its variants instead.
        for template in self:
            template.pricelist_item_count = template.env[
                "product.pricelist.item"
            ].search_count(
                [
                    "&",
                    "|",
                    ("product_tmpl_id", "in", template.ids),
                    ("product_id", "in", template.product_variant_ids.ids),
                    ("pricelist_id.active", "=", True),
                ]
            )

    def open_pricelist_rules(self):
        self.ensure_one()
        # Same domain as standard but WITHOUT the compute_price='fixed' filter,
        # so formula and percentage rules are listed too.
        domain = [
            "&",
            "|",
            ("product_tmpl_id", "=", self.id),
            ("product_id", "in", self.product_variant_ids.ids),
            ("pricelist_id.active", "=", True),
        ]
        return {
            "name": _("Pricelist Rules"),
            "view_mode": "list,form",
            "views": [
                (
                    self.env.ref(
                        "xb_product_pricelist_rules."
                        "product_pricelist_item_tree_view_all"
                    ).id,
                    "list",
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
