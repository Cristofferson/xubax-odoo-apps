# -*- coding: utf-8 -*-
{
    "name": "eCommerce Tag Filter Groups – Several Tag Filters in the Shop",
    "summary": "Split the single \"Tags\" filter of the online shop into your own filter "
               "blocks (Style, Occasion, Stones…). A product can carry several tags of the "
               "same block, without creating variants or touching sales.",
    "description": """
eCommerce Tag Filter Groups
===========================

Odoo's online shop can filter by product tags, but all tags land in **one single
"Tags" block**, and ticking two of them always shows products that have *either*
tag. As soon as tags describe different things — the *style* of a ring and the
*number of stones* — the filter becomes a mixed list that customers cannot use.

Attributes are not the answer either: an attribute with several values on the same
product becomes an option the customer has to *choose* on the product page, in the
cart and at the Point of Sale.

This module adds **Tag Filter Groups**:

* Create groups such as **Style**, **Stones** or **Occasion** in
  *Website ▸ eCommerce ▸ Products ▸ Tag Filter Groups* and put tags in them.
* The shop shows **one filter block per group**, with its own title, both in the
  sidebar and in the *Filters* panel (mobile / top bar layout).
* **Several tags per product**, in the same group or not: a ring can be *Eternity*
  and *Promise* at the same time.
* **Smart combination**, like attribute filters: tags of the **same group** are
  combined with **OR**, tags of **different groups** with **AND**
  (*Style = Eternity or Promise* **and** *Stones = Solitaire*).
* Tags without a group keep working exactly as in standard Odoo, under "Tags".

Nothing else changes: tags do not create variants, prices, internal references,
order lines or Point of Sale pop-ups. Uninstalling the module brings back the
standard single "Tags" block.

Configuration
-------------
1. Enable *Filter by Tags* in the shop (Website editor ▸ Shop page ▸ Tags).
2. Create your groups and assign tags to them.
3. Make sure the tags are *Visible to customers* and set on published products.

Compatibility
-------------
* Odoo 19.0, Community and Enterprise.
* Depends only on ``website_sale``.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Website/eCommerce",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "price": 15.00,
    "currency": "USD",
    "depends": [
        "website_sale",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/product_tag_group_views.xml",
        "views/templates.xml",
    ],
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
}
