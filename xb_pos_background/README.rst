============================================================
POS Background – Your Own Image and Logo on the Point of Sale
============================================================

Replaces the default Odoo background image and the Odoo logo of the Point of
Sale with your own, chosen **per register** from the standard POS settings.

The screens it dresses
======================

* **Standby screen** — where the register waits between sales, with the clock.
* **Cashier login screen** — shown when the *Cashiers* option (``pos_hr``) is
  enabled.
* **POS top bar** — the logo in the middle, when no order is open.

Configuration
=============

*Settings ▸ Point of Sale ▸ (your register) ▸ XUBAX - Background & Logo*

============================  ==============================================
Setting                       What it does
============================  ==============================================
Background image              Replaces the default Odoo artwork.
Background colour             Painted behind the image; on its own, a flat
                              brand colour with no image.
Image fit                     Fill the screen / fit the whole image / tile /
                              centre.
Darkening (%)                 0–80 % of black over the picture, so the clock
                              and the buttons stay readable.
Clock                         Automatic (default), dark or light.
POS logo                      Odoo logo, company logo, or a custom upload.
============================  ==============================================

How it works
============

Odoo draws those screens through CSS custom properties that the Point of Sale
never fills in:

.. code-block:: scss

    // point_of_sale/static/src/app/screens/login_screen/login_screen.scss
    .login-overlay {
        background: {
            color: var(--homeMenu-bg-color, #{$o-gray-200});
            image: var(--homeMenu-bg-image, url(".../background-light.svg"));
        }
    }
    // point_of_sale/static/src/app/components/navbar/navbar.scss
    .pos-logo { background-image: var(--navbar-logo, url(".../odoo_logo.svg")); }

The module fills those variables in on the ``.pos`` root element, per register.
No core stylesheet is overwritten and no core template is patched, so a Point of
Sale with nothing configured is identical to a plain Odoo.

Two details worth knowing
-------------------------

**The images never travel in the POS loading payload.**
``pos.config._load_pos_data_fields()`` returns ``[]``, so the Point of Sale
reads *every* stored field of the register: an untouched ``fields.Image`` would
be sent base64-encoded to every terminal on every session load. Both images are
stripped from that payload in ``_load_pos_data_read()`` and sent as
``/web/image`` URLs instead, carrying the attachment checksum as the
cache-busting token — so the address changes when the picture changes, and *not*
when some unrelated POS setting is saved.

**The clock follows the background.**
Odoo writes the clock and the date in dark grey, which disappears over a dark
photograph. ``xb_bg_is_dark`` is computed from the perceived brightness of the
uploaded image (read down to 16×16), the background colour and the darkening
percentage; when the result is dark, the clock is turned white with a soft
shadow.

Not included on purpose
=======================

The **customer display** background is a standard Odoo 19 feature
(``pos.config.customer_display_bg_img``, in *Settings ▸ Point of Sale ▸ Customer
Display*). This module does not duplicate it.

Testing
=======

.. code-block:: bash

    odoo-bin -d <db> -u xb_pos_background --test-enable \
             --test-tags /xb_pos_background --stop-after-init

Credits
=======

* Author: Cristofferson Reyes — XUBAX
* Support: soporte@xubax.com
* License: OPL-1
