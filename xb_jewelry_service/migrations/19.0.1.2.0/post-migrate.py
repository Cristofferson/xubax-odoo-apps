from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Re-point the laser shot, which noupdate data would otherwise freeze.

    The laser inscription photo used to be asked for on any diamond. Most
    stones carry no inscription, so it was a shot the counter could never
    take, with the customer waiting. It now applies only when the piece is
    marked as inscribed.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    kind = env.ref("xb_jewelry_service.photo_kind_laser", raise_if_not_found=False)
    if kind and kind.condition == "diamond":
        kind.condition = "diamond_laser"
