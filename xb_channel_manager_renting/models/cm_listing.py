# -*- coding: utf-8 -*-
from odoo import fields, models


class CmListingRenting(models.Model):
    _inherit = "xb.cm.listing"

    product_tmpl_id = fields.Many2one(domain=[("rent_ok", "=", True)])

    def _nightly_price(self):
        """Best nightly price from the rental pricing of the product."""
        self.ensure_one()
        tmpl = self.product_tmpl_id
        pricing = tmpl.product_pricing_ids.filtered(
            lambda p: p.recurrence_id.unit in ("day", "night")
            or "night" in (p.recurrence_id.name or "").lower())
        if not pricing:
            pricing = tmpl.product_pricing_ids
        return pricing[:1].price or super()._nightly_price()
