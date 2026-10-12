# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    xb_tf_layout = fields.Selection([
        ('fab', 'Floating button'),
        ('bar', 'Always-visible bar'),
        ('line', 'Text line'),
        ('dots', 'Main filter in view'),
    ], string='Kiosk Filters Layout', default='fab', required=True,
        help='Floating button: a small "Filter" button opens a panel with every filter.\n'
             'Always-visible bar: every filter as a row of options above the products.\n'
             'Text line: a discreet line under the categories with what is chosen; it opens the panel.\n'
             'Main filter in view: the first filter (e.g. Metal) stays in view, the rest in the panel.')
    xb_tf_icons = fields.Selection([
        ('none', 'None'),
        ('color', 'Tag color'),
        ('jewelry', 'Jewelry drawings'),
    ], string='Kiosk Filter Drawings', default='color', required=True,
        help='Tag color: a dot with the color of each tag (when it has one).\n'
             'Jewelry drawings: stone shapes (Round, Princess, Oval…) and metal colors (White '
             'gold, Yellow gold, Rose gold…), recognised by the option name.')
    xb_tf_show_count = fields.Boolean(
        string='Kiosk Filters: Show Counts', default=True,
        help='Each option shows how many products it leaves.')
    xb_tf_categ_ids = fields.Many2many(
        'pos.category', 'xb_tf_pos_config_pos_category_rel', string='Kiosk Filters: Categories',
        help='The kiosk categories that offer filters. Empty: every category with something '
             'to filter.')
    xb_tf_color_ink = fields.Char(
        string='Kiosk Filters: Main Color',
        help='Buttons and chosen options. Empty: the kiosk theme color.')
    xb_tf_color_accent = fields.Char(
        string='Kiosk Filters: Highlight Color',
        help='Frame of the chosen options and counters. Empty: the kiosk theme color.')

    def _xb_tf_settings(self):
        self.ensure_one()
        return {
            'layout': self.xb_tf_layout or 'fab',
            'icons': self.xb_tf_icons or 'color',
            'show_count': self.xb_tf_show_count,
            'categ_ids': self.xb_tf_categ_ids.ids,
            'ink': self.xb_tf_color_ink or False,
            'accent': self.xb_tf_color_accent or False,
        }

    @api.model
    def _load_pos_self_data_read(self, records, config):
        read_records = super()._load_pos_self_data_read(records, config)
        if read_records:
            read_records[0]['_xb_tf'] = config.sudo()._xb_tf_settings()
        return read_records
