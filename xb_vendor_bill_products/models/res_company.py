# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # -- Unknown products -----------------------------------------------
    xb_vbp_mode = fields.Selection(
        selection=[
            ('off', "Disabled"),
            ('propose', "Propose for review"),
            ('auto', "Create automatically"),
        ],
        string="Unknown products on vendor bills",
        default='propose',
        required=True,
        help="What to do when a line of an imported vendor bill refers to a "
             "product that is not in the catalogue yet.",
    )
    xb_vbp_categ_id = fields.Many2one(
        comodel_name='product.category',
        string="Category for new products",
        help="Left empty, Odoo's default category is used.",
    )
    xb_vbp_product_type = fields.Selection(
        selection=[('consu', "Goods"), ('service', "Service")],
        string="Type for new products",
        default='consu',
        required=True,
    )
    xb_vbp_is_storable = fields.Boolean(
        string="Track inventory on new products",
        default=True,
        help="Only applies to goods, and only when Inventory is installed. "
             "A product created without this flag never moves stock.",
    )
    xb_vbp_set_barcode = fields.Boolean(
        string="Use the standard item identifier as barcode",
        default=True,
        help="Electronic invoices may carry a GTIN/EAN for the item. When it "
             "is not used by another product, it is set as the barcode.",
    )
    xb_vbp_set_default_code = fields.Boolean(
        string="Use the vendor code as internal reference",
        default=False,
        help="Off by default: the vendor's code is their code, not yours, and "
             "two vendors may use the same one. It is always stored on the "
             "vendor pricelist regardless of this setting.",
    )

    # -- Cost ------------------------------------------------------------
    xb_vbp_cost_policy = fields.Selection(
        selection=[
            ('never', "Never"),
            ('first', "Only the first time"),
            ('always', "Always"),
        ],
        string="Update cost from the bill",
        default='first',
        required=True,
        help="Never: the bill price is only informative.\n"
             "Only the first time: the price is recorded when the product and "
             "the vendor are first linked, and never touched again.\n"
             "Always: every bill updates the vendor price and the cost.",
    )
    xb_vbp_update_standard_price = fields.Boolean(
        string="Also update the product cost",
        default=True,
        help="Besides the vendor pricelist, write the bill price on the "
             "product's Cost field. Only done when the product's costing "
             "method is Standard Price, so automated FIFO/AVCO valuations "
             "are never disturbed.",
    )
    xb_vbp_margin_percent = fields.Float(
        string="Sale price margin (%)",
        default=0.0,
        help="Applied on the cost to propose a sale price for products "
             "created from a bill. Zero leaves the sale price at zero.",
    )

    # -- Images ----------------------------------------------------------
    xb_vbp_image_mode = fields.Selection(
        selection=[
            ('off', "Disabled"),
            ('propose', "Propose candidates"),
            ('auto', "Attach the best match"),
        ],
        string="Product images",
        default='off',
        required=True,
        help="Look for a picture for products that do not have one. The "
             "search runs in a scheduled action, never during the import.",
    )
    xb_vbp_image_provider = fields.Selection(
        selection=[
            ('duckduckgo', "DuckDuckGo (no API key)"),
            ('google_cse', "Google Programmable Search (API key)"),
        ],
        string="Image search engine",
        default='duckduckgo',
        required=True,
    )
    xb_vbp_image_google_key = fields.Char(string="Google API key")
    xb_vbp_image_google_cx = fields.Char(string="Google search engine ID")
    xb_vbp_image_candidates = fields.Integer(
        string="Candidates per product",
        default=6,
    )
    xb_vbp_image_min_px = fields.Integer(
        string="Minimum image side (px)",
        default=400,
        help="Candidates smaller than this on their shortest side are "
             "discarded.",
    )
    xb_vbp_image_query_suffix = fields.Char(
        string="Add to every image search",
        help="Appended to the product description when searching, to steer "
             "the results. For example a brand, or \"producto\".",
    )
