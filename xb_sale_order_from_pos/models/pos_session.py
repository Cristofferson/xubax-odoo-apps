# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS
# Odoo 17 loads the register's data through pos.session loaders.
from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_res_company(self):
        # Expose the resolved issuer RFC (the receipt footer shows the fiscal entity's
        # RFC, the parent's for a branch) and the layaway terms the register checks.
        result = super()._loader_params_res_company()
        result["search_params"]["fields"].extend([
            "xb_cfdi_emisor_rfc", "xb_layaway_down_percent", "xb_order_down_percent",
            "xb_layaway_min_payment", "xb_layaway_warn_reserved",
        ])
        return result
