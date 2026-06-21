Product Pricelist Rules – All Types & Search
============================================

Show **all** pricelist rules on the product smart button, search products
inside any pricelist, and add a searchable Price Rules menu for Odoo 18.

* Author: **Cristofferson Reyes** (XUBAX)
* License: LGPL-3 (free)
* Compatible with: **Odoo 18.0** Enterprise and Community

The problem
-----------

In Odoo 18 the **Pricelist Rules** smart button on the product form only
counts and opens rules whose computation is *Fixed Price*. Rules based on a
**formula** (``Cost`` + margin) or a **percentage discount** are hidden: the
button shows ``0`` and opens an empty list, even if the product is referenced
by many pricelist rules.

On top of that, the **Price Rules** tab inside a pricelist is a plain scroll
with no search box, and the rules search view only lets you *group by* product,
never type a product name. On pricelists holding thousands of per-product rules,
finding a single product is impractical.

What this module does
---------------------

* The product **Pricelist Rules** smart button counts **every** applicable
  rule (Fixed, Percentage and Formula), on the template or its variants.
* The smart button opens an informative list (pricelist, computation, base,
  margin, resulting price) instead of one that forces a meaningless
  "Fixed Price" column.
* Every pricelist form gets a **Search products / rules** button that opens
  that pricelist's rules in a real, searchable list.
* The rules search view gains a **Product** field, so you can type a product
  name to find its rules (matches both product and variant rules), in the
  whole catalog or within a single pricelist.
* Adds a menu **Sales ▸ Products ▸ Price Rules (search)** that opens the full
  list of rules with the search view (filter / group by product, pricelist,
  ...).

Installation
------------

1. Copy the ``xb_product_pricelist_rules`` folder into your Odoo addons path
   (e.g. ``/odoo/custom-addons``).
2. Restart the Odoo server::

       sudo service odoo-server restart

3. Activate developer mode and update the app list.
4. Search for *Product Pricelist Rules* in **Apps** and click **Install**.

There is nothing to configure: the smart button works immediately and the
new menu appears under **Sales ▸ Products**.

Note about other Odoo versions
------------------------------

Odoo **17.0** and **19.0** are not affected by the smart-button limitation;
on those series the smart button already lists formula rules. A dedicated
17.0 build of this module ships only the searchable Price Rules menu.

Support
-------

soporte@xubax.com · https://www.xubax.com
