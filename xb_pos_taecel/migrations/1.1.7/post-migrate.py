# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Refresh the cashier manual: the carrier picker gained a search box, tabs
    and a most-sold row, and the manual still described one long list.

    install_manual() leaves a manual a person has edited alone. Up to 1.1.6 its
    checksum never matched what was stored, so every manual looked edited and
    none would have been refreshed; it now also trusts the last writer.
    """
    from odoo.addons.xb_pos_taecel import manual
    env = api.Environment(cr, SUPERUSER_ID, {})
    manual.install_manual(env)
