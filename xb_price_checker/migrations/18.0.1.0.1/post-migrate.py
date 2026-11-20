from odoo import SUPERUSER_ID, api

from odoo.addons.xb_price_checker import manual


def migrate(cr, version):
    """Databases that already had the app get the manual too."""
    manual.install_manual(api.Environment(cr, SUPERUSER_ID, {}))
