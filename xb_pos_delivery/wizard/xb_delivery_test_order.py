# -*- coding: utf-8 -*-
import secrets

from odoo import fields, models, _
from odoo.exceptions import UserError


class XbDeliveryTestOrder(models.TransientModel):
    """Simulate an incoming delivery order without any API credentials.

    Lets merchants demo/validate the whole flow (POS alert, accept, kitchen,
    ready, payment) before the platform connection is live.
    """
    _name = 'xb.delivery.test.order'
    _description = 'Delivery Test Order'

    account_id = fields.Many2one(
        'xb.delivery.account', required=True,
        default=lambda self: self.env['xb.delivery.account'].search([], limit=1))
    order_type = fields.Selection(
        [('delivery', 'Delivery'), ('pickup', 'Pickup')], default='delivery',
        required=True)
    product_ids = fields.Many2many(
        'product.template', string='Products',
        domain="[('available_in_pos', '=', True)]")
    cash_order = fields.Boolean(string='Cash Order')

    def action_create_test_order(self):
        self.ensure_one()
        account = self.account_id
        if not account.config_id.current_session_id:
            raise UserError(_(
                'Open a session on %s first, so the test order can reach the '
                'POS.', account.config_id.name))
        templates = self.product_ids
        if not templates:
            templates = account._menu_products()[:2]
        if not templates:
            raise UserError(_('No POS products found to build the test order.'))
        items = []
        total = 0.0
        for template in templates:
            price = account._menu_price(template)
            total += price
            items.append({
                'ref': str(template.id),
                'name': template.name,
                'qty': 1,
                'unit_price': price,
                'options': [],
                'note': '',
            })
        external_id = 'TEST-%s' % secrets.token_hex(4).upper()
        norm = {
            'external_id': external_id,
            'display_id': external_id[-5:],
            'type': self.order_type,
            'note': _('TEST ORDER — do not prepare'),
            'prep_time': account.default_prep_time,
            'cash_due': total if self.cash_order else 0.0,
            'customer': {'name': _('Test Customer'), 'phone': '5550000000'},
            'items': items,
            'charges': [],
            'discounts': [],
            'raw': {'test': True},
        }
        order = account._process_incoming_order(norm)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'res_id': order.id,
            'view_mode': 'form',
        }
