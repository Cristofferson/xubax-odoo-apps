# -*- coding: utf-8 -*-
from odoo import Command
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestVendorBillProducts(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vendor = cls.env['res.partner'].create({'name': "Vendor Uno"})
        cls.company = cls.env.company
        cls.company.write({
            'xb_vbp_mode': 'propose',
            'xb_vbp_cost_policy': 'first',
            'xb_vbp_image_mode': 'off',
        })

    def _new_bill(self):
        return self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor.id,
            'invoice_date': '2026-01-15',
        })

    def _data(self, **kwargs):
        vals = {
            'code': 'V-001',
            'name': "Cable HDMI 2 m",
            'barcode': False,
            'price_unit': 100.0,
            'quantity': 3.0,
            'uom_id': False,
            'product_id': False,
        }
        vals.update(kwargs)
        return vals

    # -- matching -------------------------------------------------------
    def test_match_uses_vendor_code(self):
        """The vendor's own code lives on the vendor pricelist, not on our
        internal reference."""
        product = self.env['product.product'].create({
            'name': "Cable HDMI",
            'default_code': 'INT-99',
        })
        self.env['product.supplierinfo'].create({
            'partner_id': self.vendor.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_code': 'V-001',
        })
        bill = self._new_bill()
        found = bill._xb_vbp_handle_line(self._data())
        self.assertEqual(found, product)

    def test_match_falls_back_to_odoo(self):
        product = self.env['product.product'].create({
            'name': "Cable HDMI 2 m",
            'default_code': 'HDMI2',
        })
        bill = self._new_bill()
        found = bill._xb_vbp_handle_line(self._data(product_id=product.id))
        self.assertEqual(found, product)

    def test_match_ignores_other_vendor_code(self):
        """The same code from a different vendor must not match."""
        other = self.env['res.partner'].create({'name': "Vendor Dos"})
        product = self.env['product.product'].create({'name': "Otra cosa"})
        self.env['product.supplierinfo'].create({
            'partner_id': other.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_code': 'V-001',
        })
        bill = self._new_bill()
        found = bill._xb_vbp_handle_line(self._data(name="Producto inexistente"))
        self.assertFalse(found)

    # -- proposals ------------------------------------------------------
    def test_unknown_item_creates_one_proposal_and_counts(self):
        bill = self._new_bill()
        self.assertFalse(bill._xb_vbp_handle_line(self._data()))
        proposal = self.env['xb.bill.product.proposal'].search([
            ('partner_id', '=', self.vendor.id), ('vendor_code', '=', 'V-001')])
        self.assertEqual(len(proposal), 1)
        self.assertEqual(proposal.occurrence_count, 1)

        second = self._new_bill()
        second._xb_vbp_handle_line(self._data(price_unit=120.0))
        proposal.invalidate_recordset()
        self.assertEqual(proposal.occurrence_count, 2)
        self.assertEqual(proposal.price_unit, 120.0)
        self.assertEqual(len(proposal.move_ids), 2)

    def test_proposal_creates_product_and_learns_code(self):
        bill = self._new_bill()
        bill._xb_vbp_handle_line(self._data())
        proposal = self.env['xb.bill.product.proposal'].search([
            ('vendor_code', '=', 'V-001')], limit=1)
        proposal.action_create_product()
        self.assertEqual(proposal.state, 'done')
        product = proposal.product_id
        self.assertTrue(product)
        self.assertEqual(product.name, "Cable HDMI 2 m")

        # The next bill from the same vendor matches on its own.
        again = self._new_bill()
        self.assertEqual(again._xb_vbp_handle_line(self._data()), product)

    def test_link_existing_product_learns_code(self):
        product = self.env['product.product'].create({'name': "Ya existía"})
        bill = self._new_bill()
        bill._xb_vbp_handle_line(self._data())
        proposal = self.env['xb.bill.product.proposal'].search([
            ('vendor_code', '=', 'V-001')], limit=1)
        proposal.product_id = product
        proposal.action_link_product()
        self.assertEqual(proposal.state, 'done')
        again = self._new_bill()
        self.assertEqual(again._xb_vbp_handle_line(self._data()), product)

    def test_auto_mode_creates_the_product(self):
        self.company.xb_vbp_mode = 'auto'
        bill = self._new_bill()
        product = bill._xb_vbp_handle_line(self._data())
        self.assertTrue(product)
        self.assertTrue(product.product_tmpl_id.xb_vbp_auto_created)
        self.assertEqual(product.product_tmpl_id.xb_vbp_origin_move_id, bill)

    def test_off_mode_does_nothing(self):
        self.company.xb_vbp_mode = 'off'
        bill = self._new_bill()
        self.assertFalse(bill._xb_vbp_handle_line(self._data()))
        self.assertFalse(self.env['xb.bill.product.proposal'].search([
            ('vendor_code', '=', 'V-001')]))

    # -- cost policy ----------------------------------------------------
    def _product_with_seller(self):
        product = self.env['product.product'].create({
            'name': "Con proveedor", 'standard_price': 0.0})
        self.env['product.supplierinfo'].create({
            'partner_id': self.vendor.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_code': 'V-001',
        })
        return product

    def test_cost_policy_never(self):
        self.company.xb_vbp_cost_policy = 'never'
        product = self._product_with_seller()
        self._new_bill()._xb_vbp_handle_line(self._data())
        self.assertEqual(product.standard_price, 0.0)
        self.assertEqual(product.seller_ids.price, 0.0)

    def test_cost_policy_first_only(self):
        self.company.xb_vbp_cost_policy = 'first'
        product = self._product_with_seller()
        self._new_bill()._xb_vbp_handle_line(self._data(price_unit=100.0))
        self.assertEqual(product.seller_ids.price, 100.0)
        self.assertTrue(product.seller_ids.xb_vbp_cost_synced)
        # A later, dearer bill must not move it.
        self._new_bill()._xb_vbp_handle_line(self._data(price_unit=180.0))
        self.assertEqual(product.seller_ids.price, 100.0)

    def test_cost_policy_always(self):
        self.company.xb_vbp_cost_policy = 'always'
        product = self._product_with_seller()
        self._new_bill()._xb_vbp_handle_line(self._data(price_unit=100.0))
        self._new_bill()._xb_vbp_handle_line(self._data(price_unit=180.0))
        self.assertEqual(product.seller_ids.price, 180.0)

    def test_cost_ignores_discount_free_lines(self):
        self.company.xb_vbp_cost_policy = 'always'
        product = self._product_with_seller()
        self._new_bill()._xb_vbp_handle_line(self._data(price_unit=0.0))
        self.assertFalse(product.seller_ids.xb_vbp_cost_synced)

    # -- back-fill ------------------------------------------------------
    def test_backfill_keeps_the_imported_figures(self):
        bill = self._new_bill()
        bill.write({'invoice_line_ids': [Command.create({
            'name': "Cable HDMI 2 m",
            'quantity': 3.0,
            'price_unit': 100.0,
        })]})
        bill._xb_vbp_handle_line(self._data())
        proposal = self.env['xb.bill.product.proposal'].search([
            ('vendor_code', '=', 'V-001')], limit=1)
        proposal.action_create_product()

        line = bill.invoice_line_ids[0]
        self.assertEqual(line.product_id, proposal.product_id)
        self.assertEqual(line.price_unit, 100.0)
        self.assertEqual(line.quantity, 3.0)
        self.assertEqual(line.name, "Cable HDMI 2 m")
