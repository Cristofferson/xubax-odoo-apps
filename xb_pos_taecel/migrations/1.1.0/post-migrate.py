# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Bill payments now carry the provider charge, the XPago fee and the business fee: read the catalog again
    right after the update (in the cron, not here, so a slow provider never blocks the update)."""
    # A 19.0 database already on 1.1.x ran this before: re-running it on the move to 20.0
    # would put back a $2 fee someone set to 0 on purpose.
    if version and tuple(int(x) for x in version.split('.')[-3:]) >= (1, 1, 0):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Businesses XUBAX registered (affiliates of the XPago network) pay the $2 XPago fee per bill payment.
    env['xb.taecel.account'].with_context(active_test=False).search([
        ('role', '=', 'affiliate'), ('xpago_fee', '=', 0)]).xpago_fee = 2.0
    cron = env.ref('xb_pos_taecel.cron_taecel_catalog', raise_if_not_found=False)
    if cron:
        cron._trigger()
