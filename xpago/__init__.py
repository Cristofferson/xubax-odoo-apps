from . import controllers
from . import models

import odoo.addons.payment as payment  # Prevent circular import error with payment (res.country).

from .upgrade import fold_old_modules


def pre_init_hook(env):
    # A database that had the former XPago card payments app keeps its records, settings and payments.
    fold_old_modules(env.cr, 'xpago')


def post_init_hook(env):
    payment.setup_provider(env, 'xpago')


def uninstall_hook(env):
    payment.reset_payment_provider(env, 'xpago')
