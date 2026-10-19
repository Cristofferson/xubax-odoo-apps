# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    # Managers only: the kiosk runs as a public user and the point of sale
    # loads every field of its config, so an unrestricted link to the wall
    # would ask a cashier or the kiosk for rights on the wall's settings.
    xb_showroom_screen_id = fields.Many2one(
        'xb.showroom.screen', string='Showroom wall',
        groups='point_of_sale.group_pos_manager',
        domain="[('company_id', '=', company_id)]",
        help="The kiosk's product page gets a button that shows the piece on "
             "this wall. Only products ticked 'Show on the showroom wall'.")

    def _xb_showroom_kiosk_screen(self):
        """The wall this kiosk may drive, or an empty recordset."""
        self.ensure_one()
        config = self.sudo()
        if config.self_ordering_mode != 'kiosk':
            return self.env['xb.showroom.screen']
        return config.xb_showroom_screen_id

    @api.model
    def _load_pos_self_data_read(self, records, config):
        read_records = super()._load_pos_self_data_read(records, config)
        if read_records:
            # A yes/no is all the kiosk needs to show the button.
            read_records[0]['_xb_showroom_kiosk'] = bool(config._xb_showroom_kiosk_screen())
        return read_records
