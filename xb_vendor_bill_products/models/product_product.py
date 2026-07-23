# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    @api.model
    def _xb_vbp_vendor_partners(self, partner):
        """The vendor and its commercial entity: a bill may be addressed to a
        child contact while the pricelist is kept on the parent."""
        if not partner:
            return self.env['res.partner']
        return partner | partner.commercial_partner_id

    @api.model
    def _xb_vbp_match_vendor_product(self, partner, data, company=None):
        """Find a product from what *this vendor* calls it.

        Odoo's own ``_retrieve_product`` compares the vendor's item code with
        our internal reference, which rarely matches. The vendor pricelist is
        where that translation lives, so we look there first.

        :param partner: the vendor (``res.partner``)
        :param data: dict with ``code`` / ``name`` keys read from the file
        :return: a ``product.product``, empty if nothing matched
        """
        company = company or self.env.company
        partners = self._xb_vbp_vendor_partners(partner)
        code = (data.get('code') or '').strip()
        name = (data.get('name') or '').strip().split('\n', 1)[0]
        if not partners or not (code or name):
            return self.browse()

        Supplierinfo = self.env['product.supplierinfo'].sudo()
        base_domain = [
            ('partner_id', 'in', partners.ids),
            *Supplierinfo._check_company_domain(company),
        ]
        candidates = []
        if code:
            candidates.append(base_domain + [('product_code', '=', code)])
        if name:
            candidates.append(base_domain + [('product_name', '=', name)])
        for domain in candidates:
            for seller in Supplierinfo.search(domain, limit=20):
                # A pricelist line set on a template with several variants and
                # no variant chosen is ambiguous: skip it rather than guess.
                if not seller.product_id and len(seller.product_tmpl_id.product_variant_ids) > 1:
                    continue
                product = seller.product_id or seller.product_tmpl_id.product_variant_id
                if product:
                    return product.with_env(self.env)
        return self.browse()

    # ------------------------------------------------------------------
    # Vendor pricelist + cost
    # ------------------------------------------------------------------
    def _xb_vbp_get_or_create_seller(self, partner, data, move=None, create=True):
        """Return the ``product.supplierinfo`` linking this product to the
        vendor, creating it (and thereby learning the vendor's code) when it
        does not exist yet."""
        self.ensure_one()
        company = (move.company_id if move else False) or self.env.company
        partners = self._xb_vbp_vendor_partners(partner)
        if not partners:
            return self.env['product.supplierinfo']
        Supplierinfo = self.env['product.supplierinfo'].sudo()
        seller = Supplierinfo.search(
            [
                ('partner_id', 'in', partners.ids),
                ('product_tmpl_id', '=', self.product_tmpl_id.id),
                *Supplierinfo._check_company_domain(company),
            ],
            limit=1,
        )
        code = (data.get('code') or '').strip()
        name = (data.get('name') or '').strip()
        if seller:
            # Learn the code without ever overwriting one already there.
            updates = {}
            if code and not seller.product_code:
                updates['product_code'] = code
            if name and not seller.product_name:
                updates['product_name'] = name
            if updates:
                seller.write(updates)
            return seller
        if not create:
            return Supplierinfo.browse()
        vals = {
            'partner_id': (partner.commercial_partner_id or partner).id,
            'product_tmpl_id': self.product_tmpl_id.id,
            'product_code': code or False,
            'product_name': name or False,
            'company_id': company.id,
        }
        if len(self.product_tmpl_id.product_variant_ids) > 1:
            vals['product_id'] = self.id
        return Supplierinfo.create(vals)

    def _xb_vbp_sync_from_bill(self, move, partner, data):
        """Apply the company's cost policy and remember the vendor's code."""
        self.ensure_one()
        company = move.company_id or self.env.company
        seller = self._xb_vbp_get_or_create_seller(partner, data, move=move)
        if not seller:
            return
        policy = company.sudo().xb_vbp_cost_policy
        if policy == 'never':
            return
        if policy == 'first' and seller.xb_vbp_cost_synced:
            return

        price = data.get('price_unit') or 0.0
        if float_is_zero(price, precision_digits=6):
            return

        seller_vals = {
            'price': price,
            'currency_id': (move.currency_id or company.currency_id).id,
            'xb_vbp_cost_synced': True,
            'xb_vbp_last_move_id': move.id,
        }
        if data.get('uom_id') and 'product_uom_id' in seller._fields:
            seller_vals['product_uom_id'] = data['uom_id']
        seller.sudo().write(seller_vals)

        if company.sudo().xb_vbp_update_standard_price:
            self._xb_vbp_write_standard_price(move, price)

    def _xb_vbp_write_standard_price(self, move, price):
        """Write the cost, but only where it is safe to do so."""
        self.ensure_one()
        company = move.company_id or self.env.company
        # Never disturb an automated FIFO/AVCO valuation.
        cost_method = getattr(self.product_tmpl_id, 'cost_method', 'standard')
        if cost_method and cost_method != 'standard':
            return
        currency = move.currency_id or company.currency_id
        date = move.invoice_date or move.date or fields.Date.context_today(self)
        cost = currency._convert(price, company.currency_id, company, date)
        self.sudo().with_company(company).standard_price = cost

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------
    @api.model
    def _xb_vbp_default_categ(self, product_type):
        """A product with no category is awkward to report on, so fall back to
        the one Odoo ships for that kind of product."""
        xmlids = ['product.product_category_goods', 'product.product_category_all']
        if product_type == 'service':
            xmlids.insert(0, 'product.product_category_services')
        for xmlid in xmlids:
            categ = self.env.ref(xmlid, raise_if_not_found=False)
            if categ:
                return categ
        return self.env['product.category'].search([], limit=1)

    @api.model
    def _xb_vbp_prepare_product_vals(self, company, data):
        company = company.sudo()
        name = (data.get('name') or '').strip() or (data.get('code') or '').strip()
        vals = {
            'name': name or _("Unnamed product"),
            'type': company.xb_vbp_product_type,
            'purchase_ok': True,
            'xb_vbp_auto_created': True,
        }
        categ = company.xb_vbp_categ_id or self._xb_vbp_default_categ(
            company.xb_vbp_product_type)
        if categ:
            vals['categ_id'] = categ.id
        if company.xb_vbp_set_default_code and data.get('code'):
            vals['default_code'] = data['code']
        if company.xb_vbp_product_type == 'consu' and 'is_storable' in self.env['product.template']._fields:
            vals['is_storable'] = company.xb_vbp_is_storable
        if data.get('uom_id'):
            vals['uom_id'] = data['uom_id']
        barcode = (data.get('barcode') or '').strip()
        if barcode and company.xb_vbp_set_barcode:
            taken = self.sudo().with_context(active_test=False).search_count(
                [('barcode', '=', barcode)])
            if not taken:
                vals['barcode'] = barcode
        return vals

    @api.model
    def _xb_vbp_create_from_bill(self, move, partner, data):
        """Create a product out of a bill line and wire it to the vendor."""
        company = (move.company_id or self.env.company).sudo()
        vals = self._xb_vbp_prepare_product_vals(company, data)
        vals['xb_vbp_origin_move_id'] = move.id
        product = self.sudo().with_company(company).create(vals)

        # Cost first: the sale price may be derived from it.
        forced = dict(data)
        product._xb_vbp_sync_from_bill(move, partner, forced)
        margin = company.xb_vbp_margin_percent
        if margin and product.standard_price:
            product.sudo().with_company(company).list_price = \
                product.standard_price * (1.0 + margin / 100.0)

        if company.xb_vbp_image_mode != 'off':
            product.product_tmpl_id.sudo().xb_vbp_image_state = 'pending'
        move.sudo().message_post(body=_(
            "Product created from this bill: %s", product.display_name))
        return product.with_env(self.env)
