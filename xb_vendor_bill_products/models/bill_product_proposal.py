# -*- coding: utf-8 -*-
import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class XbBillProductProposal(models.Model):
    _name = 'xb.bill.product.proposal'
    _description = "Product Proposed by a Vendor Bill"
    _order = 'state, occurrence_count desc, last_seen desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string="Description",
        required=True,
        help="The description exactly as it arrived on the vendor's file.",
    )
    vendor_code = fields.Char(
        string="Vendor code",
        help="The reference the vendor uses for this item.",
    )
    barcode = fields.Char(string="Barcode / GTIN")
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Vendor",
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string="Currency",
    )
    price_unit = fields.Float(
        string="Last price",
        digits='Product Price',
    )
    quantity = fields.Float(
        string="Last quantity",
        digits='Product Unit',
    )
    uom_id = fields.Many2one(comodel_name='uom.uom', string="Unit")
    extra_code = fields.Char(
        string="Classification",
        help="Any classification code carried by the file, such as the "
             "Mexican CFDI ClaveProdServ.",
    )

    move_id = fields.Many2one(
        comodel_name='account.move',
        string="Last bill",
        ondelete='set null',
    )
    move_ids = fields.Many2many(
        comodel_name='account.move',
        string="Seen on",
        help="Every bill this item has arrived on.",
    )
    occurrence_count = fields.Integer(string="Times seen", default=1)
    first_seen = fields.Datetime(default=fields.Datetime.now, readonly=True)
    last_seen = fields.Datetime(default=fields.Datetime.now, readonly=True)

    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Product",
        ondelete='set null',
        help="Set it to link this item to a product you already have, or "
             "leave it empty and let the proposal create one.",
    )
    state = fields.Selection(
        selection=[
            ('draft', "To review"),
            ('done', "Applied"),
            ('rejected', "Rejected"),
        ],
        default='draft',
        required=True,
        index=True,
    )
    note = fields.Text(string="Notes")

    image_state = fields.Selection(
        selection=[
            ('pending', "Searching"),
            ('proposed', "Candidates found"),
            ('done', "Image chosen"),
            ('failed', "Nothing found"),
        ],
        string="Image search",
        readonly=True,
    )
    image_candidate_ids = fields.One2many(
        comodel_name='xb.bill.product.image',
        inverse_name='proposal_id',
        string="Image candidates",
    )
    image_1920 = fields.Image(string="Chosen image", max_width=1920, max_height=1920)

    _uniq_vendor_code = models.Constraint(
        'unique(company_id, partner_id, vendor_code)',
        "This vendor code is already proposed for this vendor.",
    )

    # ------------------------------------------------------------------
    # Registration from the import
    # ------------------------------------------------------------------
    @api.model
    def _xb_dedupe_domain(self, move, partner, data):
        company = move.company_id or self.env.company
        domain = [
            ('company_id', '=', company.id),
            ('partner_id', '=', (partner.commercial_partner_id or partner).id),
        ]
        code = (data.get('code') or '').strip()
        if code:
            return domain + [('vendor_code', '=', code)]
        name = (data.get('name') or '').strip()
        return domain + [('vendor_code', 'in', (False, '')), ('name', '=ilike', name)]

    @api.model
    def _xb_register(self, move, partner, data):
        """Record an unknown bill item for review, or bump the one already
        recorded. Returns the proposal."""
        company = move.company_id or self.env.company
        partner = partner.commercial_partner_id or partner
        vals_common = {
            'price_unit': data.get('price_unit') or 0.0,
            'quantity': data.get('quantity') or 0.0,
            'currency_id': (move.currency_id or company.currency_id).id,
            'move_id': move.id,
            'last_seen': fields.Datetime.now(),
        }
        if data.get('uom_id'):
            vals_common['uom_id'] = data['uom_id']

        existing = self.sudo().search(self._xb_dedupe_domain(move, partner, data), limit=1)
        if existing:
            vals = dict(vals_common)
            vals['occurrence_count'] = existing.occurrence_count + 1
            if move not in existing.move_ids:
                vals['move_ids'] = [Command.link(move.id)]
            if not existing.barcode and data.get('barcode'):
                vals['barcode'] = data['barcode']
            if not existing.extra_code and data.get('extra_code'):
                vals['extra_code'] = data['extra_code']
            existing.write(vals)
            return existing

        vals = dict(vals_common)
        vals.update({
            'name': (data.get('name') or data.get('code') or _("Unnamed item")).strip(),
            'vendor_code': (data.get('code') or '').strip() or False,
            'barcode': (data.get('barcode') or '').strip() or False,
            'extra_code': data.get('extra_code') or False,
            'partner_id': partner.id,
            'company_id': company.id,
            'move_ids': [Command.link(move.id)],
        })
        if company.sudo().xb_vbp_image_mode != 'off':
            vals['image_state'] = 'pending'
        return self.sudo().create(vals)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _xb_as_data(self):
        self.ensure_one()
        return {
            'code': self.vendor_code,
            'name': self.name,
            'barcode': self.barcode,
            'price_unit': self.price_unit,
            'quantity': self.quantity,
            'uom_id': self.uom_id.id or False,
            'extra_code': self.extra_code,
        }

    def action_create_product(self):
        """Create the product and back-fill the bills it came from."""
        for proposal in self:
            if proposal.state == 'done':
                continue
            if proposal.product_id:
                raise UserError(_(
                    "%s is already linked to a product. Use \"Link\" instead.",
                    proposal.name))
            move = proposal.move_id or proposal.move_ids[:1]
            if not move:
                raise UserError(_(
                    "%s has no bill to take the company and currency from.",
                    proposal.name))
            product = self.env['product.product']._xb_vbp_create_from_bill(
                move, proposal.partner_id, proposal._xb_as_data())
            if proposal.image_1920:
                product.product_tmpl_id.sudo().write({
                    'image_1920': proposal.image_1920,
                    'xb_vbp_image_state': 'done',
                })
            proposal.write({'product_id': product.id, 'state': 'done'})
            proposal._apply_to_moves()
        return True

    def action_link_product(self):
        """Attach the item to the product chosen in the Product field, and
        teach Odoo the vendor's code so the next bill matches on its own."""
        for proposal in self:
            if not proposal.product_id:
                raise UserError(_(
                    "Choose a product on \"%s\" before linking it.", proposal.name))
            move = proposal.move_id or proposal.move_ids[:1]
            data = proposal._xb_as_data()
            if move:
                proposal.product_id._xb_vbp_sync_from_bill(
                    move, proposal.partner_id, data)
            else:
                proposal.product_id._xb_vbp_get_or_create_seller(
                    proposal.partner_id, data)
            proposal.state = 'done'
            proposal._apply_to_moves()
        return True

    def action_reject(self):
        self.write({'state': 'rejected'})
        return True

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
        return True

    def action_search_images(self):
        self.env['xb.product.image.finder']._fill_candidates_for_proposals(
            self, force=True)
        return True

    def action_open_bills(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Bills"),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.move_ids.ids)],
        }

    # ------------------------------------------------------------------
    # Back-fill
    # ------------------------------------------------------------------
    def _apply_to_moves(self):
        """Put the product on the lines of the draft bills where this item
        appeared, without touching the amounts that were imported."""
        self.ensure_one()
        if not self.product_id:
            return
        label = (self.name or '').strip()
        for move in self.move_ids.filtered(lambda m: m.state == 'draft'):
            lines = move.invoice_line_ids.filtered(
                lambda line: not line.product_id and (line.name or '').strip() == label
            )
            for line in lines:
                self._apply_to_line(line)

    def _apply_to_line(self, line):
        """Set the product on a bill line and restore what the file said.

        Writing ``product_id`` makes Odoo recompute the description, price,
        taxes and unit from the product. On an imported bill that would
        silently rewrite the vendor's own figures, so they are put back.
        """
        snapshot = {
            'quantity': line.quantity,
            'price_unit': line.price_unit,
            'discount': line.discount,
        }
        if line.name:
            snapshot['name'] = line.name
        taxes = line.tax_ids.ids
        line = line.with_context(check_move_validity=False)
        line.write({'product_id': self.product_id.id})
        restore = dict(snapshot)
        restore['tax_ids'] = [Command.set(taxes)]
        line.write(restore)
