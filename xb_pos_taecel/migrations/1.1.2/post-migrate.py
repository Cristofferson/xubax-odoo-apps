# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """The service cost now carries the XPago fee inside it (the customer never sees that fee on its own line):
    recompute the stored figures of every service with the new rule."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['xb.taecel.carrier'].with_context(active_test=False).search([])._compute_customer_fee()
