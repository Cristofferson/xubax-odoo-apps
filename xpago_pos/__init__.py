from . import models
from . import receipt
from . import wizard

from odoo.addons.xpago.upgrade import fold_old_modules


def pre_init_hook(env):
    # A database that had the former XPago point of sale app keeps its records, settings and charges.
    fold_old_modules(env.cr, 'xpago_pos')
