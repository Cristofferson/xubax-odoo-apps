Changelog
=========

19.0.1.8.0 (2026-08)
--------------------

* **Fix (critical): no reminder was ever sent on Odoo 19.** ``res.partner``
  dropped the ``mobile`` field in Odoo 19, and ``_send`` still read
  ``partner.mobile``. The resulting ``AttributeError`` was swallowed by the
  cron's ``except``, so every SMS and WhatsApp send silently did nothing —
  no error anywhere in the interface. The number is now read defensively.
* **Fix (critical): upgrading any module could freeze the whole database.**
  Translations were reloaded from a ``_register_hook`` that opened its own
  database cursor. During an ``-i``/``-u`` of *any* module, that cursor asked
  for rows the upgrade transaction already had locked, and neither side could
  move — PostgreSQL cannot break the tie because one side is blocked in
  Python, not in SQL. The ``except Exception: pass`` around it protected
  against the reload failing, not against it hanging. The reload now runs from
  the manifest's ``post_init_hook`` on install and from a ``<function>`` on
  upgrade, both inside the cursor that is already open.
* **New trigger: at the start of the event's month.** Fires on the 1st of the
  month the event falls in, whatever the exact day — the natural cadence for
  "we are celebrating you this month" campaigns, which the N-days-before
  trigger cannot express.
* **Fix: schedule lines showed a blank channel name.** ``_compute_display_name``
  read ``field.selection`` directly, which holds the *method name* when the
  selection is method-based (as ``channel`` is, so add-ons can extend it).
  It now resolves through ``fields_get``.

19.0.1.7.0 (2026-07)
--------------------

* **Technical name renamed** ``special_dates`` → ``xb_special_dates`` for
  consistency with the rest of the XUBAX catalogue (all modules use the
  ``xb_`` vendor prefix). Fresh installs are unaffected. Databases that
  already had ``special_dates`` installed must run the one-off rename
  migration shipped in ``migrations/`` (see ``README``) — it renames the
  module, its records (external IDs) and the ``pos_popup_interval_hours``
  system parameter, preserving all data.

19.0.1.6.3 (2026-06)
--------------------

* **Multiple events per ticket are no longer lost.** Pending captures
  are now kept as an ordered per-order *task list* instead of a flat set,
  and the capture popups are *chained*: when one closes the next pending
  event is surfaced (re-draining on ``onClose``). Previously each drain
  trigger showed only one popup and never re-drained, so a ticket with
  3+ distinct events silently dropped the extras at payment. A
  per-order "shown this chain" set (reset when the partner is set and at
  pay) keeps a ``Later``-postponed event from re-appearing instantly
  while still resurfacing it on the next trigger.
* **Product in several trigger categories: the cashier now chooses.**
  ``_xbCaptureForProduct`` returns *every* matching event (de-duplicated
  by wish type) instead of silently taking the first. When a single
  product maps to more than one event type the popup shows a selector so
  the cashier picks which one to register; the chosen type is saved.
* **Anti-duplicate guard preserved across the new flow.** Settled events
  are tracked at two levels (per wish type and per task) on top of the
  unchanged server-side 90-day ``check_existing_for_capture`` check, so
  the same event is never asked twice for an order.

19.0.1.6.2 (2026-06)
--------------------

* **Fix: POS capture popup never appeared.** ``_xbCaptureForProduct``
  read ``pos_categ_ids`` from the order line's ``product.product``
  variant, which is empty in the POS (the field is loaded for
  ``product.template`` only). The proxy never falls through to the
  template because the variant *inherits* the field via ``_inherits``,
  so it returns the variant's empty value. Now reads
  ``product.product_tmpl_id.pos_categ_ids`` explicitly, with defensive
  fallbacks.
* **Single-popup re-entry guard.** A ``_xbCaptureDialogOpen`` flag
  ensures only one capture popup is on screen regardless of which path
  triggers it (product added, partner set, pre-payment drain). Local
  state is now settled before the ``create_from_pos`` RPC and rolled
  back on error.
* **Translations regenerated.** ``es`` / ``es_MX`` / ``.pot`` rebuilt
  against the current module — the POS-capture feature added ~146 new
  strings (the ``Triggers Reminder Type`` field, capture/today popups,
  emoji selection labels, help texts) that were previously untranslated.

19.0.1.5.2 (2026-05)
--------------------

* **Translations complete.** Spanish (es) and Spanish-MX (es_MX)
  translations now cover every visible string: field labels, help
  texts, selection values, menus, actions, view body text, and the
  bundled email template. References (``#:`` lines) match the live
  Odoo XML IDs exactly, so the bundled .po files are applied
  immediately on install/upgrade with no manual reload.
* **Auto-reload on every upgrade.** A ``_register_hook`` on
  ``xb.wish.type`` invokes ``TranslationImporter(...overwrite=True)``
  every time the module is loaded — never any "Reload Translations"
  button to click.
* **"Today" menu placed before "Configuration"** under Contacts
  (sequence 2 vs Odoo's Configuration sequence 3).
* Flattened multi-line ``<p>`` texts in the form views so their
  msgids match the bundled .po entries.

19.0.1.4.x (2026-05)
--------------------

* **Live "Today" dashboard.** Replaced the cron-fed
  ``xb.wish.reminders.today`` table with a server action that
  computes due-today reminders live, in Python, every time the menu
  opens. Reminders created today appear immediately.
* **Status fields on every Reminder.**

  * ``Comms Status`` (``✓ 2/2 sent``, ``⏳ 1/3 sent``, ``—``)
  * ``Activities Status`` same idea, for auto-activities.
  * ``Next Occurrence`` showing the upcoming future date.
* **mail.thread + mail.activity.mixin** on
  ``xb.wish.reminders`` — full chatter and activity sidebar on every
  reminder.
* **"Run Daily Cron Now" button** on Reminder Type so admins can
  trigger the full cron flow on demand for testing.
* **Modern Odoo 19 icon** — diagonal vibrant gradient, iOS-style
  squircle, glassmorphism highlight, sparkles, calendar tile with
  drop shadow and accent heart.
* **Modern Selection widget for emojis** — picking the icon of a
  Reminder Type is now a dropdown of 30 curated emojis with
  descriptive labels (🎂 Birthday, 💍 Wedding/Engagement, ...).
* Removed redundant ``mail_template_id`` on the Reminder Type — the
  Communications tab is now the single source of truth.

19.0.1.3.x (2026-05)
--------------------

* **POS popup behaviour redesigned.**

  * Welcome popup at session open showing the list of every customer
    with a special date today.
  * Periodic re-show every N hours (default 3, configurable via the
    ``xb_special_dates.pos_popup_interval_hours`` system parameter).
  * Individual popup when a customer with a date today is selected on
    the current order.
  * Granular per-Reminder-Type control via ``show_in_pos`` flag.
* **Menus consolidated under Contacts.** Sales and Point of Sale
  parent menus removed; everything now lives at
  *Contacts ▸ Special Dates*.
* **Frontend rewrite.** All POS interactions go through async RPC
  after session load; no more ``_load_pos_data_fields`` or
  ``pos.load.mixin`` (those were breaking POS price/tax
  bootstrapping with a ``currency_id`` undefined error).
* OWL Navbar template inheritance removed — replaced with a single
  ``PosStore`` patch that survives Odoo 19 frontend reorganisations.

19.0.1.2.x (2026-05)
--------------------

* **Odoo 19 compatibility pass.**

  * ``res.groups.category_id`` → ``res.groups.privilege``.
  * ``res.groups.users`` → ``res.groups.user_ids``.
  * Removed ``ir.cron.numbercall`` and ``doall`` (removed in 19).
  * Smart-button compute methods made public (no leading underscore).
  * ``<group expand="0" string="Group By">`` removed from search
    views (Odoo 19 search panels can't parse it).
  * ``view_mode`` set to ``list`` instead of ``tree``.
  * ``target="inline"`` replaced with ``target="current"``.

19.0.1.1.0 (2026-05)
--------------------

* **Multi-channel communication schedule** per Reminder Type.
  Stack as many lines as you need (Email -7d, SMS -1d, Email day-of).
  Each line records its own ``last_sent`` and ``sent_count``.
* **Auto-activities.** Configure any ``mail.activity.type`` (Call,
  Email, To-Do, Meeting, custom) to be created on the customer's
  record when the date arrives.
* **Optional WhatsApp channel** through the companion add-on
  ``xb_special_dates_whatsapp`` (auto-installs when Odoo's ``whatsapp``
  module is present).

19.0.1.0.0 (2026-05)
--------------------

* Initial release for Odoo 19.
* Models, security, multi-company rules, OWL POS popup, daily cron,
  Spanish translations, marketing assets for apps.odoo.com.
