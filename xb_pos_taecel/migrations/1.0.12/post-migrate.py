# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Give databases upgrading from an older version the cashier manual too.

    The manual is created by the module's post_init_hook, which only runs on a
    fresh install -- so without this, every shop already running the module
    would be the only one without it. install_manual() is idempotent and does
    nothing where Knowledge is not installed.
    """
    from odoo.addons.xb_pos_taecel import manual
    env = api.Environment(cr, SUPERUSER_ID, {})
    manual.install_manual(env)
