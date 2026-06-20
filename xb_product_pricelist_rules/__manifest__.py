# -*- coding: utf-8 -*-
{
    "name": "Product Pricelist Rules – All Types & Search",
    "summary": "Show ALL pricelist rules (formula/percentage too) on the "
               "product smart button, plus a searchable Price Rules menu.",
    "description": """
Product Pricelist Rules – All Types & Search
============================================

In Odoo 18 the **Pricelist Rules** smart button on the product form only
counts and opens rules whose computation is a *Fixed Price*. Any rule based
on a **formula** (``Cost`` + margin) or a **percentage discount** is silently
hidden: the smart button shows ``0`` and opens an empty list, even when the
product is referenced by dozens of pricelist rules.

This module fixes that and adds a searchable rules menu:

Key features
------------
* The product **Pricelist Rules** smart button now counts **every** rule
  applicable to the product or its variants (Fixed, Percentage and Formula),
  not only fixed-price ones.
* Clicking the smart button opens an **informative list** showing the
  pricelist, how the price is computed, the base, the margin and the
  resulting price — instead of a list that forces a meaningless "Fixed Price"
  column on formula rules.
* A new menu **Sales ▸ Products ▸ Price Rules (search)** opens the full list
  of pricelist rules with the standard search view, so you can finally
  filter and group thousands of rules by product, pricelist, etc.
* No data migration, no configuration: install and the smart button is fixed.

Compatibility
-------------
* Odoo 18.0 Community and Enterprise.
* Note: Odoo 17.0 and 19.0 are not affected by this smart-button limitation;
  on those versions a dedicated build ships only the searchable menu.
""",
    "author": "Cristofferson Reyes",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Sales/Sales",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "depends": [
        "product",
        "sale",
    ],
    "data": [
        "views/pricelist_item_views.xml",
    ],
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
}
