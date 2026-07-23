# -*- coding: utf-8 -*-
import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    xb_vbp_proposal_ids = fields.One2many(
        comodel_name='xb.bill.product.proposal',
        inverse_name='move_id',
        string="Proposed products",
    )
    xb_vbp_proposal_count = fields.Integer(
        compute='_compute_xb_vbp_proposal_count')

    def _compute_xb_vbp_proposal_count(self):
        counts = dict(self.env['xb.bill.product.proposal']._read_group(
            [('move_ids', 'in', self.ids)],
            groupby=['move_ids'],
            aggregates=['__count'],
        ))
        for move in self:
            move.xb_vbp_proposal_count = counts.get(move, 0)

    def action_xb_vbp_open_proposals(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Proposed products"),
            'res_model': 'xb.bill.product.proposal',
            'view_mode': 'list,form',
            'domain': [('move_ids', 'in', self.ids)],
        }

    # ------------------------------------------------------------------
    # Import hook
    # ------------------------------------------------------------------
    def _extend_with_attachments(self, files_data, new=False):
        """Let the decoders know which bill they are filling.

        The format-specific decoders reach the catalogue through models taken
        from ``self.env``, so the bill travels down to them in the context.
        """
        return super(
            AccountMove,
            self.with_context(xb_vbp_move_id=self.id),
        )._extend_with_attachments(files_data, new=new)

    def _xb_vbp_handle_line(self, data):
        """Resolve one imported bill line into a product.

        This is the single entry point every file format goes through.

        :param data: ``code``, ``name``, ``barcode``, ``price_unit``,
            ``quantity``, ``uom_id``, ``extra_code`` and the ``product_id``
            Odoo matched on its own, if any.
        :return: the product to put on the line, possibly empty.
        """
        self.ensure_one()
        Product = self.env['product.product']
        if not self.is_purchase_document(include_receipts=True):
            return Product.browse(data.get('product_id') or [])

        company = (self.company_id or self.env.company).sudo()
        partner = self.partner_id.commercial_partner_id or self.partner_id
        product = Product.browse(data.get('product_id') or [])

        # What this vendor calls the item beats a fuzzy name match.
        matched = Product._xb_vbp_match_vendor_product(partner, data, company=company)
        if matched:
            product = matched

        if product:
            try:
                product._xb_vbp_sync_from_bill(self, partner, data)
            except Exception as err:  # noqa: BLE001 - an import must not die here
                _logger.warning(
                    "Could not sync product %s from bill %s: %s",
                    product.display_name, self.id, err)
            return product

        if not partner:
            return Product.browse()

        mode = company.xb_vbp_mode
        try:
            if mode == 'auto':
                return Product._xb_vbp_create_from_bill(self, partner, data)
            if mode == 'propose':
                self.env['xb.bill.product.proposal']._xb_register(self, partner, data)
        except Exception as err:  # noqa: BLE001
            _logger.warning(
                "Could not handle unknown item %r on bill %s: %s",
                data.get('name'), self.id, err)
        return Product.browse()
