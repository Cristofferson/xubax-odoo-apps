from odoo.addons.xpago.upgrade import fold_old_modules


def migrate(cr, version):
    # The point of sale and kiosk bridges join the app: their records, settings and charges stay as they were.
    fold_old_modules(cr, 'xpago')
