# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    xb_va_auto_wall = fields.Boolean(
        "Puts the piece on the wall by itself", default=True,
        help="When the seller opens a piece the customer wants to see, it also goes to the wall "
             "(if the piece can be shown there), without waiting for the customer to ask.")
    xb_va_follow_wall = fields.Boolean(
        "The seller goes to the wall", default=True,
        help="When the seller sends a piece to the wall, it also appears small on the wall, with its "
             "subtitles, and its voice comes from the wall speakers (the kiosk stays quiet).")
