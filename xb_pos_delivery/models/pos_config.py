# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .. import const


class PosConfig(models.Model):
    _inherit = 'pos.config'

    xb_delivery_account_ids = fields.One2many(
        'xb.delivery.account', 'config_id', string='Delivery Platforms')
    xb_delivery_active = fields.Boolean(
        compute='_compute_xb_delivery_active')

    @api.depends('xb_delivery_account_ids.active')
    def _compute_xb_delivery_active(self):
        for config in self:
            config.xb_delivery_active = bool(config.xb_delivery_account_ids)

    def get_xb_delivery_data(self):
        """Order counters + provider info for the POS UI badge/popup."""
        self.ensure_one()
        session = self.current_session_id
        counts = {}
        total_new = 0
        if session:
            grouped = self.env['pos.order']._read_group(
                [('session_id', '=', session.id),
                 ('xb_delivery_account_id', 'in', self.xb_delivery_account_ids.ids),
                 ('state', '!=', 'cancel')],
                ['xb_delivery_account_id', 'xb_delivery_status'], ['__count'])
            for account, status, count in grouped:
                data = counts.setdefault(account.provider, {
                    'awaiting': 0, 'preparing': 0, 'done': 0})
                if status == 'placed':
                    data['awaiting'] += count
                    total_new += count
                elif status == 'accepted':
                    data['preparing'] += count
                elif status in ('ready', 'dispatched', 'delivered'):
                    data['done'] += count
        providers = [{
            'id': account.id,
            'provider': account.provider,
            'name': dict(const.PROVIDERS)[account.provider],
            'state': account.state,
        } for account in self.xb_delivery_account_ids]
        return {
            'counts': counts,
            'providers': providers,
            'total_new': total_new,
        }

    def xb_set_store_status(self, account_id, online):
        """Called from the POS UI toggle."""
        self.ensure_one()
        account = self.xb_delivery_account_ids.filtered(
            lambda a: a.id == account_id)
        if account:
            account.sudo()._set_store_status(online)
        return True
