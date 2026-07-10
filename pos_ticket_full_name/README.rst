POS Receipt – Full Product Name (no truncation)
===============================================

Print the **complete product name** on Point of Sale receipts. Long names wrap
onto several lines instead of being cut off with an ellipsis.

* Author: **Cristofferson Reyes** (XUBAX)
* License: LGPL-3 (free)
* Compatible with: **Odoo 18.0** Enterprise and Community

The problem
-----------

Odoo applies the Bootstrap class ``text-truncate`` (``overflow: hidden``) to the
product name of each order line. On the **printed receipt** that clips long
product names to a single line, so the ticket reads like::

    1  Shampoo Anticaspa con Keratin…      $120.00

and neither the cashier nor the customer can read the full product name. Tickets
printed as an image through an **Epson / IoT thermal printer** are the most
affected, because the receipt is rasterised and the name stays on one line.

What this module does
---------------------

* Prints the product name **in full**, wrapping onto as many lines as needed::

      1  Shampoo Anticaspa con           $120.00
         Keratina y Biotina Frasco 750ml

* Fixes the printed ticket (Epson / IoT raster) as well as the on-screen preview.
* Over-long words (codes / SKUs without spaces) are also broken so nothing is
  ever clipped.
* The fix is **scoped to the receipt** (``.pos-receipt``): the on-screen cart
  keeps its compact, truncated look, where space is limited.
* **Pure CSS** — no Python, no data, nothing to configure.

Installation
------------

1. Copy the ``pos_ticket_full_name`` folder into your Odoo addons path
   (e.g. ``/odoo/custom-addons``).
2. Restart the Odoo server::

       sudo service odoo-server restart

3. Activate developer mode and update the app list.
4. Search for *POS Receipt – Full Product Name* in **Apps** and click
   **Install**.
5. Reopen (or refresh) the Point of Sale in the browser so the new stylesheet
   is loaded.

There is nothing to configure: the next receipt already shows the full name.

Support
-------

soporte@xubax.com · https://www.xubax.com
