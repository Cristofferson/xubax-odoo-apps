# -*- coding: utf-8 -*-
"""Hook into Odoo's UBL / Factur-X / CII import.

``_retrieve_line_vals`` is the one place where a line of the file has been
fully read — product identifiers, quantity and price at once — and it is
shared by every format built on ``account.edi.common``, so a single override
covers all of them.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountEdiCommon(models.AbstractModel):
    _inherit = 'account.edi.common'

    def _retrieve_line_vals(self, tree, document_type=False, qty_factor=1):
        vals = super()._retrieve_line_vals(
            tree, document_type=document_type, qty_factor=qty_factor)
        move_id = self.env.context.get('xb_vbp_move_id')
        if not move_id:
            return vals
        move = self.env['account.move'].browse(move_id).exists()
        if not move:
            return vals

        try:
            xpath_dict = self._get_line_xpaths(document_type, qty_factor)
            raw = {
                key: self._find_value(xpath, tree)
                for key, xpath in (xpath_dict.get('product') or {}).items()
            }
        except Exception as err:  # noqa: BLE001 - never break the import
            _logger.debug("Could not read product identifiers: %s", err)
            return vals

        discount = vals.get('discount') or 0.0
        price_unit = vals.get('price_unit') or 0.0
        product = move._xb_vbp_handle_line({
            'code': raw.get('default_code'),
            'name': raw.get('name') or vals.get('name'),
            'barcode': raw.get('barcode'),
            'price_unit': price_unit * (1.0 - discount / 100.0),
            'quantity': vals.get('quantity') or 0.0,
            'uom_id': vals.get('product_uom_id') or False,
            'product_id': vals.get('product_id') or False,
        })
        if product:
            vals['product_id'] = product.id
        return vals
