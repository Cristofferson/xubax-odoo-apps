from . import controllers
from . import models

from odoo.addons.xpago.upgrade import fold_old_modules


def pre_init_hook(env):
    # A database that had the former XPago kiosk app keeps its records.
    fold_old_modules(env.cr, 'xpago_self_order')
