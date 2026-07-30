# -*- coding: utf-8 -*-
{
    'name': 'Xibo Connector',
    'version': '19.0.1.6.5',
    'category': 'Marketing/Digital Signage',
    'summary': 'Manage Xibo CMS digital signage from Odoo: displays, media, datasets, layouts, broadcasts.',

    'description': """
Xibo Connector for Odoo 19
===========================

The professional bridge between your Odoo and your Xibo CMS digital signage
network. Manage screens, upload media, schedule layouts and trigger real-time
content updates without leaving Odoo.

This is the **base module** of the Xibo Connector Suite. Add-on modules for
Point of Sale, Frontdesk, Sales, eCommerce and Daily Content Feeds are sold
separately.

Key Features
------------
* Multi-server, multi-company configuration (OAuth2 client_credentials)
* Automatic token caching and refresh
* Sync displays, display groups, layouts and DataSets from Xibo
* Upload, edit and delete media (images, videos, audio) to the Xibo Library
* **Sync** existing Library media metadata from Xibo (read-only references)
* **Quick Display**: turn any image into a one-click on-screen message
* Schedule layouts via the Broadcast model (overlay, fullscreen, ticker)
* Day-of-week and time-of-day filters
* Recurrence (minutely, hourly, daily, weekly, monthly, yearly)
* Trigger real-time refresh via the CMS REST API (no port 9505 exposure)
* Full audit trail of every Xibo API call
* Open-in-Xibo deep links from every relevant record
* Granular access rights (User / Manager)
* English and Spanish (Mexico) translations

Compatibility
-------------
* Odoo 19.0
* Xibo CMS v3.0 or newer (older versions may have reduced functionality)

Prerequisites
-------------
* A running Xibo CMS you administer
* OAuth2 application credentials in Xibo (Administration -> Applications)
* Python ``requests`` library on the Odoo server

Support
-------
soporte@xubax.com

Changelog
---------
19.0.1.6.4 (2026-07)
~~~~~~~~~~~~~~~~~~~~
* **Scheduling from Odoo went to the CMS in the wrong hour.** Xibo reads
  every scheduling date in the CMS's own local time and Odoo stores them in
  UTC, so a broadcast set for 10:00 reached a CMS in Mexico City as 04:00 —
  accepted by both systems, wrong on screen. Odoo now learns the CMS clock
  offset from the CMS itself (``/api/clock``) and shifts the dates, so a
  daylight-saving change fixes itself with no setting to maintain.
* **Broadcasts of a layout were rejected outright.** The display groups were
  sent under a key stripped of its ``[]``, which the CMS answers with
  *422 Invalid Argument displayGroupIds*. Only ticker broadcasts worked.
* **New: displays can be marked as ignoring instant changes.** Some players
  never act on a real-time layout change even though the CMS accepts the
  order, and only ever play what is on their schedule. Ticking *Player
  Ignores Instant Changes* makes Odoo schedule the content for exactly as
  long as it is needed and ask the player to collect, instead of relying on
  the push alone. Entries created this way are tracked and removed
  automatically, so the CMS calendar does not fill up with dead events.

19.0.1.6.3 (2026-07)
~~~~~~~~~~~~~~~~~~~~
* **Displays now carry their screen geometry.** ``xibo.display`` stores the
  orientation and resolution the player reports, plus the CMS resolution
  that matches it. New ``_layout_geometry()`` returns the canvas any layout
  aimed at that screen must use, so child modules stop hard-coding
  1920x1080 — a portrait screen gets a portrait layout and a 3x1 videowall
  gets the whole wall instead of only its middle panel.
* New ``xibo.server._resolution_catalogue()`` / ``_match_resolution()``:
  map a reported screen size onto a CMS resolution, matching exactly when
  possible and otherwise by aspect ratio (never by pixel count, which is
  what silently letterboxed videowalls).
* ``change_layout()`` now sends ``downloadRequired`` so a player that never
  cached the layout fetches it instead of silently staying on its schedule.
* Fixed: contacts whose ``xibo_show_in_public_screens`` was never set kept
  a NULL, which reads as "hide" — their name was replaced by the anonymous
  greeting on screen even though the field defaults to "show". A migration
  normalises those rows; explicit opt-outs are preserved.

19.0.1.6.2 (2026-05)
~~~~~~~~~~~~~~~~~~~~
* New helper ``xibo.server._dataset_insert_row(dataset_xibo_id, row_data)``:
  thin wrapper around ``POST /api/dataset/data/{datasetId}`` that accepts
  ``row_data`` as a ``{column_heading: value}`` dict and internally resolves
  each heading to its ``dataSetColumnId_X`` form using the synced column
  metadata. Enables direct-XMR scenarios (e.g. POS AI Thank-You Camino B)
  without going through the Broadcast scheduler.
* No schema changes; safe upgrade from 19.0.1.6.1.

19.0.1.6.1 (2026-05)
~~~~~~~~~~~~~~~~~~~~
* AI nickname automation on res.partner (native ai.agent + base.automation).
* XMR ``changeLayout`` / ``revertToSchedule`` (Xibo 3.x+ name).
* ``change_layout()`` accepts ``campaign_xibo_id`` (stable across publishes).
* Privacy field ``xibo_show_in_public_screens`` on res.partner.
    """,

    'author': 'Cristofferson Reyes Rodriguez',
    'maintainer': 'Cristofferson Reyes Rodriguez',
    'website': 'https://www.xubax.com',
    'support': 'soporte@xubax.com',
    'license': 'OPL-1',
    'price': 18.00,
    'currency': 'USD',

    'depends': [
        'base',
        'mail',
        'ai',
        'base_automation',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/xibo_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'data/ai_server_actions.xml',
        'data/ai_automation.xml',
        'views/xibo_server_views.xml',
        'views/xibo_display_group_views.xml',
        'views/xibo_display_views.xml',
        'views/xibo_media_views.xml',
        'views/xibo_layout_views.xml',
        'views/xibo_dataset_views.xml',
        'views/xibo_broadcast_views.xml',
        'views/xibo_event_log_views.xml',
        'views/res_partner_views.xml',
        'views/xibo_menus.xml',
        'wizards/xibo_media_upload_wizard_views.xml',
        'wizards/xibo_quick_display_wizard_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
