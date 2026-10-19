# -*- coding: utf-8 -*-
"""Pieces now have to be enabled for the wall one by one.

Until this version any published piece could be sent, so nothing that the
shop already shows may disappear on upgrade: the pieces of each screen's
shop-window category are enabled. Plain SQL on purpose, so no write()
override of product.template fires for a flag nobody else reads.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    screens = env['xb.showroom.screen'].with_context(active_test=False).search(
        [('idle_category_id', '!=', False)])
    ids = set()
    for screen in screens:
        ids.update(env['product.template'].with_context(active_test=False).search(
            [('public_categ_ids', 'child_of', screen.idle_category_id.id)]).ids)
    if ids:
        cr.execute("UPDATE product_template SET xb_showroom_enabled = TRUE WHERE id = ANY(%s)",
                   [list(ids)])
