# -*- coding: utf-8 -*-
{
    "name": "Products from Vendor Bills – create, match, price & illustrate",
    "summary": "Import a vendor bill (UBL / Factur-X / XML) and Odoo learns the "
               "products: matches the vendor's own item codes, proposes the "
               "unknown ones for review, creates them, keeps the cost up to "
               "date and even finds a product image.",
    "description": """
Products from Vendor Bills
==========================

Odoo already reads an electronic vendor bill and fills the lines for you. What
it does **not** do is deal with the products: if the item on the XML is not
already in your catalogue, the line is left with a bare text label — no
product, no stock, no cost, no traceability. And nothing is remembered, so the
**same bill next month fails to match again**.

This module closes that gap.

Matching that actually works
----------------------------
Odoo matches the vendor's item code against **your** internal reference, which
almost never matches. This module looks first at the **vendor pricelist**
(``product.supplierinfo``): the code *that vendor* uses for *your* product. And
every time you confirm a match, it is **written back**, so the next bill from
that vendor matches on its own. The catalogue teaches itself.

Order of matching:

1. Vendor item code stored on the vendor pricelist (learned).
2. Vendor item name stored on the vendor pricelist.
3. Odoo's standard search: barcode, internal reference, name.

Unknown products: proposed, not silently invented
-------------------------------------------------
Three modes, per company:

* **Disabled** — standard Odoo behaviour, nothing happens.
* **Propose for review** *(default)* — every unknown item lands in
  *Proposed Products*, a review screen with the description, the vendor, the
  code, the price, how many times it has been seen and on which bills. You
  create it, link it to an existing product, or reject it. One click also
  back-fills the bills where it appeared.
* **Create automatically** — the product is created during the import, with
  the category, type and unit you configured.

Repeated items are grouped into a single proposal with a counter, so twelve
bills from the same vendor do not give you twelve rows to review.

Cost: you decide the policy
---------------------------
The single most requested behaviour, and the one that must never be a
surprise. Per company:

* **Never** — the price on the bill is only informative.
* **Only the first time** *(default)* — the cost is set when the product and
  the vendor are first linked, and never touched again. Ideal when purchase
  prices move and you do not want your valuation moving with them.
* **Always** — every bill updates the vendor price and the cost.

The vendor pricelist price is always kept in the bill's own currency. The
product cost is converted to the company currency, and is only written when
the product's costing method is *Standard Price* — automated FIFO/AVCO
valuations are never disturbed.

Optionally, a sale price can be derived from the cost with a margin.

Product images, found for you
-----------------------------
A catalogue built from bills is a catalogue with no pictures. This module can
look for one:

* **Disabled** *(default)*.
* **Propose candidates** — several images per product, shown side by side in
  the review screen; you pick the right one.
* **Attach the best match** — the first valid result is attached.

Two search back ends are included: **DuckDuckGo**, which needs no API key at
all, and **Google Programmable Search**, if you already have a key. Searching
runs in a scheduled action, never during the import, so importing a bill is
never slowed down or made to depend on the internet.

*You are responsible for making sure you have the right to use any image you
attach. The module only helps you find candidates — review them.*

Configuration
-------------
*Accounting ▸ Configuration ▸ Settings ▸ Products from Vendor Bills.*
Everything is per company.

Technical notes
---------------
* Extends the standard import (``account.edi.common``) — every format Odoo
  can read benefits from it, now and in the future.
* CFDI 4.0 (Mexico) is covered by the companion module
  ``xb_vendor_bill_products_mx``, installed automatically when Odoo's Mexican
  localisation is present.
* No change to Odoo's accounting, valuation or tax logic.
* Works with or without *Purchase* and *Inventory* installed.

Compatibility
-------------
* Odoo 19.0 Community and Enterprise.
""",
    "author": "Cristofferson Reyes",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Accounting/Accounting",
    "version": "19.0.1.0.1",
    "license": "OPL-1",
    "price": 89.00,
    "currency": "USD",
    "depends": [
        "account",
        "product",
        "account_edi_ubl_cii",
    ],
    "data": [
        "security/xb_vendor_bill_products_security.xml",
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/bill_product_proposal_views.xml",
        "views/bill_product_image_views.xml",
        "views/account_move_views.xml",
        "views/product_views.xml",
        "views/product_supplierinfo_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
    ],
    "post_init_hook": "_xb_vbp_post_init",
    "application": False,
    "installable": True,
    "auto_install": False,
}
