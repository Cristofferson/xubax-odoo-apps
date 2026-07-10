Special Dates
=============

Never miss a customer's birthday, anniversary or special day.
Automatic Email / SMS / WhatsApp reminders, auto-activities, and
Point of Sale popups for Odoo 19.

* Author: **Cristofferson Reyes** (XUBAX)
* License: OPL-1 (proprietary)
* Compatible with: **Odoo 19 Enterprise** and **Community**

Upgrading from ``special_dates`` (old technical name)
-----------------------------------------------------

This module was formerly published as ``special_dates``. If a database
**already had** ``special_dates`` (or ``special_dates_whatsapp``) installed,
run the one-off rename migration in ``migration/rename_from_special_dates.sql``
before loading this version — it switches the technical name at database level
and preserves all data. Fresh installs need nothing. See that file's header for
the exact steps.

Installation
------------

1. Copy the ``xb_special_dates`` folder into your Odoo addons path
   (e.g. ``/odoo/custom-addons``).
2. Restart the Odoo server::

       sudo service odoo-server restart

3. Activate developer mode and update the app list.
4. Search for *Special Dates* in **Apps** and click **Install**.

After installation, every option lives under **Contacts ▸ Special Dates**:

* **Reminders** — every special date currently configured.
* **Today** — live list of reminders due today.
* **Reminder Types** — Birthday, Anniversary, Renewal, etc., with their
  per-channel schedule (Email / SMS / WhatsApp) and auto-activities.

Reminders are also accessible as a **Special Dates** tab inside every
Contact form.

Point of Sale
-------------

* When the cashier opens a POS session, a welcome popup lists every
  customer with a special date today.
* The popup re-appears every N hours (configurable via the
  ``xb_special_dates.pos_popup_interval_hours`` system parameter, default
  ``3``) while the session stays open.
* When the cashier picks a customer with a date today, an individual
  celebratory popup appears on the order.

Translations
------------

Spanish (``es``) and Spanish (Mexico) (``es_MX``) translations are
included and applied automatically on install and on every upgrade —
no manual reload required.

Support
-------

Bug reports & feature requests: soporte@xubax.com
