# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    # pos.config does not restrict the fields it sends to the frontend
    # (pos.load.mixin._load_pos_data_fields returns [], so read([]) reads them
    # all), which is why this flag is readable as config.xb_discuss_enabled in
    # the POS without any loading override.
    xb_discuss_enabled = fields.Boolean(
        string="Discuss in the POS",
        default=True,
        help="Show the Discuss button in the Point of Sale navbar, so cashiers "
             "can read and answer their messages without leaving the POS.",
    )
