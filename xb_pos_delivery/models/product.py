# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    xb_delivery_status_ids = fields.One2many(
        'xb.delivery.item.status', 'product_tmpl_id',
        string='Delivery Availability')

    def action_xb_toggle_delivery_availability(self):
        """Toggle sold-out on every connected delivery account of the company."""
        Status = self.env['xb.delivery.item.status']
        accounts = self.env['xb.delivery.account'].search([
            ('company_id', 'in', self.env.companies.ids)])
        for template in self:
            for account in accounts:
                status = Status.search([
                    ('account_id', '=', account.id),
                    ('product_tmpl_id', '=', template.id)], limit=1)
                if status:
                    status.is_available = not status.is_available
                else:
                    Status.create({
                        'account_id': account.id,
                        'product_tmpl_id': template.id,
                        'is_available': False,
                    })
        return True
