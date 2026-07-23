# -*- coding: utf-8 -*-
"""CFDI 4.0 lines go through the same product treatment as any other format.

The Mexican decoder does not build a dict of line values the way the UBL/CII
one does: it writes straight onto the invoice line. So the product is resolved
after the localisation has done its work, and the figures it imported are put
back untouched.
"""
import logging
import re

from odoo import Command, models

_logger = logging.getLogger(__name__)

# Odoo exports its own products as "[internal reference] name".
CODE_PREFIX = re.compile(r"^\[.*?\]\s*")


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _xb_vbp_cfdi_uom(self, clave_unidad):
        """Map the CFDI ClaveUnidad to a unit of measure, when the Mexican
        UNSPSC catalogue is available."""
        if not clave_unidad:
            return False
        Uom = self.env['uom.uom']
        if 'unspsc_code_id' not in Uom._fields:
            return False
        uom = Uom.search([('unspsc_code_id.code', '=', clave_unidad)], limit=1)
        return uom.id or False

    def _l10n_mx_edi_import_cfdi_fill_invoice_line(self, tree, line):
        res = super()._l10n_mx_edi_import_cfdi_fill_invoice_line(tree, line)
        if not self.is_purchase_document(include_receipts=True):
            return res

        description = tree.attrib.get('Descripcion') or ''
        try:
            quantity = float(tree.attrib.get('Cantidad') or 0)
            price_unit = float(tree.attrib.get('ValorUnitario') or 0)
            discount = float(tree.attrib.get('Descuento') or 0)
        except (TypeError, ValueError):
            return res
        net_price = price_unit - (discount / quantity if quantity else 0.0)

        product = self._xb_vbp_handle_line({
            'code': tree.attrib.get('NoIdentificacion'),
            'name': CODE_PREFIX.sub('', description).strip() or description,
            'barcode': False,
            'extra_code': tree.attrib.get('ClaveProdServ'),
            'price_unit': net_price,
            'quantity': quantity,
            'uom_id': self._xb_vbp_cfdi_uom(tree.attrib.get('ClaveUnidad')),
            'product_id': line.product_id.id,
        })
        if product and product != line.product_id:
            self._xb_vbp_set_line_product(line, product)
        elif not line.product_id and not line.name:
            # The localisation never writes the description, so a line it
            # could not match is left completely blank on screen. The CFDI
            # said what it was; put it back.
            line.with_context(check_move_validity=False).name = description
        return res

    def _xb_vbp_set_line_product(self, line, product):
        """Put the product on the line without letting Odoo recompute the
        description, price, discount and taxes the CFDI dictated."""
        snapshot = {
            'quantity': line.quantity,
            'price_unit': line.price_unit,
            'discount': line.discount,
        }
        if line.name:
            # Only worth restoring when there was one: the CFDI decoder leaves
            # the description empty, and blanking the product's own label
            # would leave the line unreadable.
            snapshot['name'] = line.name
        if 'l10n_mx_edi_tax_object' in line._fields:
            snapshot['l10n_mx_edi_tax_object'] = line.l10n_mx_edi_tax_object
        taxes = line.tax_ids.ids
        line = line.with_context(check_move_validity=False)
        line.write({'product_id': product.id})
        line.write(dict(snapshot, tax_ids=[Command.set(taxes)]))
