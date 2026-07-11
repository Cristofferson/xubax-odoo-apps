# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class XbDeliveryItemStatus(models.Model):
    _name = 'xb.delivery.item.status'
    _description = 'Delivery Item Availability'

    account_id = fields.Many2one('xb.delivery.account', required=True,
                                 ondelete='cascade', index=True)
    product_tmpl_id = fields.Many2one('product.template', required=True,
                                      ondelete='cascade', index=True)
    is_available = fields.Boolean(default=True,
                                  help='Uncheck to mark the product as sold '
                                       'out on the platform.')

    _account_product_uniq = models.Constraint(
        'unique(account_id, product_tmpl_id)',
        "There is already an availability entry for this product and account.",
    )

    def write(self, vals):
        res = super().write(vals)
        if 'is_available' in vals:
            self._push_availability()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered(lambda r: not r.is_available)._push_availability()
        return records

    def _push_availability(self):
        for record in self:
            account = record.account_id
            if account.state != 'connected':
                continue
            try:
                account._get_driver().set_item_availability(
                    record.product_tmpl_id, record.is_available)
                account._log('out', 'item_availability', success=True,
                             message='%s -> %s' % (record.product_tmpl_id.name,
                                                   record.is_available))
            except Exception as exc:  # noqa: BLE001 - log, do not block the UI
                _logger.warning('xb_delivery: availability push failed: %s', exc)
                account._log('out', 'item_availability', success=False,
                             message=str(exc))
