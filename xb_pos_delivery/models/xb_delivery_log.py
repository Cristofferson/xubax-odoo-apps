# -*- coding: utf-8 -*-
from odoo import api, fields, models


class XbDeliveryLog(models.Model):
    _name = 'xb.delivery.log'
    _description = 'Food Delivery Log'
    _order = 'id desc'

    account_id = fields.Many2one('xb.delivery.account', required=True,
                                 ondelete='cascade', index=True)
    company_id = fields.Many2one(related='account_id.company_id', store=True)
    direction = fields.Selection([('in', 'Incoming'), ('out', 'Outgoing')],
                                 required=True)
    event = fields.Char(required=True, index=True)
    payload = fields.Text()
    success = fields.Boolean(default=True)
    message = fields.Char()

    @api.autovacuum
    def _gc_old_logs(self):
        """Keep 30 days of logs."""
        self.search([
            ('create_date', '<', fields.Datetime.subtract(fields.Datetime.now(), days=30)),
        ]).unlink()
