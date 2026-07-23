# -*- coding: utf-8 -*-
from . import models


def _xb_vbp_post_init(env):
    """Purchase already gives the product form a vendor pricelist tab. Ours is
    only needed when Purchase is not installed, which is the common shape of a
    company that just records the bills it receives."""
    view = env.ref(
        'xb_vendor_bill_products.product_template_form_view_xb_vbp_sellers',
        raise_if_not_found=False,
    )
    if not view:
        return
    purchase_installed = env['ir.module.module'].sudo().search_count([
        ('name', '=', 'purchase'),
        ('state', 'in', ('installed', 'to upgrade')),
    ])
    view.active = not purchase_installed
