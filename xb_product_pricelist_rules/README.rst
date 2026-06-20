Product Pricelist Rules – All Types & Search
============================================

An informative pricelist-rules list on the product smart button and a
searchable Price Rules menu for Odoo 17.

* Author: **Cristofferson Reyes** (XUBAX)
* License: LGPL-3 (free)
* Compatible with: **Odoo 17.0** Enterprise and Community

What this module does
---------------------

* The product **Pricelist Rules** smart button opens an informative list
  (pricelist, computation, base, discount, resulting price) instead of the
  standard list that forces a meaningless "Fixed Price" column on
  formula/percentage rules.
* Adds a **search view** for pricelist rules (Odoo 17 ships none) and a menu
  **Sales ▸ Products ▸ Price Rules (search)** to browse the full list of
  rules and filter / group by product, pricelist or computation type.

Installation
------------

1. Copy the ``xb_product_pricelist_rules`` folder into your Odoo addons path
   (e.g. ``/odoo/custom-addons``).
2. Restart the Odoo server::

       sudo service odoo-server restart

3. Activate developer mode and update the app list.
4. Search for *Product Pricelist Rules* in **Apps** and click **Install**.

Note about other Odoo versions
------------------------------

On Odoo 17 the smart button already counts formula rules natively, so this
build focuses on the informative list and the searchable menu. The Odoo 18
build additionally fixes the smart-button count, which Odoo 18 wrongly
restricts to fixed-price rules.

Support
-------

soporte@xubax.com · https://www.xubax.com
