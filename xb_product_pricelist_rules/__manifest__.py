# -*- coding: utf-8 -*-
{
    "name": "Product Pricelist Rules – All Types & Search",
    "summary": "Informative pricelist-rules list on the product smart button "
               "and a searchable Price Rules menu.",
    "description": """
Product Pricelist Rules – All Types & Search
============================================

Manage and audit pricelist rules of every computation type (Fixed,
Percentage and Formula) more comfortably.

Key features
------------
* The product **Pricelist Rules** smart button opens an **informative list**
  showing the pricelist, how the price is computed, the base, the discount
  and the resulting price — instead of a list that forces a meaningless
  "Fixed Price" column on formula/percentage rules.
* Adds a **search view** for pricelist rules (missing in Odoo 17) and a new
  menu **Sales ▸ Products ▸ Price Rules (search)** to browse the full list
  of rules and filter / group by product, pricelist or computation type.
* No data migration, no configuration.

Compatibility
-------------
* Odoo 17.0 Community and Enterprise.
* On Odoo 17 the smart button already counts formula rules natively; this
  build focuses on the informative list and the searchable rules menu. The
  Odoo 18 build additionally fixes the smart-button count, which Odoo 18
  wrongly restricts to fixed-price rules.
""",
    "author": "Cristofferson Reyes",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Sales/Sales",
    "version": "17.0.1.0.0",
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
