==========================
Products from Vendor Bills
==========================

Odoo already reads an electronic vendor bill and fills the lines. What it does
not do is deal with the **products**: an item that is not in your catalogue
leaves the line as bare text — no product, no stock, no cost, no traceability
— and nothing is remembered, so the same bill next month fails to match again.

This module closes that gap.

Matching that actually works
============================

Odoo compares the vendor's item code against **your** internal reference,
which almost never matches. This module looks first at the **vendor pricelist**
(``product.supplierinfo``): the code *that vendor* uses for *your* product.
Every confirmed match is written back, so the next bill matches on its own.

1. Vendor item code on the vendor pricelist *(learned)*
2. Vendor item name on the vendor pricelist
3. Odoo's standard search: barcode, internal reference, name

Unknown products: proposed, not silently invented
=================================================

Per company, one of three modes:

:Disabled: standard Odoo behaviour.
:Propose for review: *(default)* the item lands in **Proposed Products** with
   the vendor, the code, the price, how many times it has been seen and on
   which bills. Create it, link it to an existing product, or reject it. One
   click also back-fills the bills where it appeared, without touching the
   amounts that were imported.
:Create automatically: the product is created during the import.

Repeated items are grouped into a single proposal with a counter.

Cost policy
===========

:Never: the bill price is only informative.
:Only the first time: *(default)* the cost is set when the product and the
   vendor are first linked, and never touched again.
:Always: every bill updates the vendor price and the cost.

The vendor pricelist price stays in the bill's currency. The product cost is
converted to the company currency and is only written when the costing method
is *Standard Price*, so automated FIFO/AVCO valuations are never disturbed.
A margin can derive a sale price from the cost.

Product images
==============

A catalogue built from bills has no pictures. The module can look for one:
**disabled**, **propose candidates** (several per product, side by side), or
**attach the best match**. Two back ends: **DuckDuckGo**, which needs no API
key, and **Google Programmable Search**. The search runs in a scheduled
action, never during the import.

*You are responsible for making sure you have the right to use any image you
attach.*

Configuration
=============

*Accounting ▸ Configuration ▸ Settings ▸ Products from Vendor Bills.*
Everything is per company.

Two menus are added under *Accounting ▸ Vendors*:

* **Proposed Products** — the review screen.
* **Vendor Codes** — the translation table between the vendor's reference and
  your product. Odoo only ships a screen for this inside *Purchase*, so
  without *Purchase* it would otherwise be invisible; the module also adds a
  *Vendors* tab to the product form in that case.

Technical notes
===============

* Extends ``account.edi.common._retrieve_line_vals``, so every format Odoo can
  read benefits — UBL, Factur-X, XRechnung, CII, and whatever comes next.
* CFDI 4.0 (Mexico) is covered by ``xb_vendor_bill_products_mx``, which
  installs itself when ``l10n_mx_edi`` is present. It also fills in the line
  description, which the Mexican decoder leaves empty.
* No change to Odoo's accounting, valuation or tax logic.
* Works with or without *Purchase* and *Inventory*.

Compatibility
=============

Odoo 19.0, Community and Enterprise.

Credits
=======

Author: Cristofferson Reyes — XUBAX — https://www.xubax.com

Support: soporte@xubax.com

License: OPL-1
