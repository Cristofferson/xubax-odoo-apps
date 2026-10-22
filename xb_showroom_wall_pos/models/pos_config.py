# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    # Managers only: the register loads every field of its config, so an
    # unrestricted link to the wall would ask each cashier for rights on the
    # wall's settings. The register only gets the id, in _load_pos_data_read.
    xb_showroom_pos_screen_id = fields.Many2one(
        'xb.showroom.screen', string='Showroom wall (register)',
        groups='point_of_sale.group_pos_manager',
        domain="[('company_id', '=', company_id)]",
        help="The register gets a 'Show on the wall' button that sends the "
             "piece to this wall. Only products ticked 'Show on the showroom wall'.")

    @api.model
    def _load_pos_data_read(self, records, config):
        read_records = super()._load_pos_data_read(records, config)
        if read_records:
            read_records[0]['_xb_showroom_screen_id'] = config.sudo().xb_showroom_pos_screen_id.id or False
        return read_records
