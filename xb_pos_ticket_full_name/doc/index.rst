POS Receipt – Full Product Name
===============================

Usage
-----

There is nothing to set up. Once the module is installed and the Point of Sale
has been reopened in the browser, every receipt prints the product name in
full.

* Sell a product whose name is long (for example
  *"Shampoo Anticaspa Con Keratina Y Biotina 750ml"*).
* Go to the payment / receipt screen, or print the ticket.
* The product name is shown complete, wrapping onto several lines, instead of
  being cut off with ``…``.

Scope
-----

The change only affects the **receipt** (its on-screen preview and the printed
ticket). The order lines in the left-hand cart of the POS keep their compact,
single-line look, because there the available width is limited on purpose.

Notes
-----

* The module is pure CSS; it does not change any data, price or product name —
  only how the existing name is displayed on the receipt.
* Because the receipt is rendered from HTML/CSS, the full name applies both to
  the preview shown on screen and to the ticket sent to the printer.
