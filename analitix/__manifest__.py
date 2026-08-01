# -*- coding: utf-8 -*-
{
    "name": "Analitix — Physical Store Intelligence",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Store intelligence on Odoo: visitor counting across any number "
               "of doors, POS conversion (ATV, UPT, revenue per visitor, "
               "density), staff exclusion, device health and a hardened "
               "ingest API for edge cameras.",
    "description": """
Analitix — Physical Store Intelligence
======================================
Not a people counter: a configurable retail-intelligence platform.

Phase 1 (this release)
----------------------

* **Stores with any number of doors.** 1, 2, 3 or more entrances per store,
  defined in configuration and never in code. A setup wizard creates the
  store, its doors and their devices in one step.
* **Hardened ingest API** (/analitix/api/v1): one API key per device, stored
  hashed, rotatable and revocable in one click, scoped to its own store only.
  HTTPS enforced. Idempotent by client-generated uuid, so a network retry
  never double-counts a crossing.
* **Device health.** Heartbeats, online/degraded/offline status, a scheduled
  check that raises an activity and an e-mail when a critical device goes
  dark, plus ingest-volume anomaly detection.
* **Emergency kill switch** per store: stop capture instantly from the UI.
* **Staff exclusion.** Employee face signatures, encrypted at rest, so team
  crossings never inflate visitor counts, whichever door they use.
* **Conversion analytics.** Hourly store aggregate crossed with POS:
  conversion rate, ATV, UPT, revenue per visitor, visitors per ticket and
  sales and traffic density per square meter, with a per-door traffic
  breakdown alongside.
* **Asynchronous job queue** so heavy work never blocks the edge response.
* **Technical dashboard** for the implementer, separate from the owner's
  commercial dashboard.

Privacy by design: no image or video is ever transmitted or stored — the edge
sends only counts and irreversible numeric embeddings, and those are encrypted
in the database.

The edge agent (Python, YOLO + ByteTrack) ships separately in the ``edge/``
folder of the repository; this addon has no computer-vision dependency: it
only receives JSON.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "company": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "license": "OPL-1",
    "depends": [
        "base",
        "mail",
        "hr",
        "point_of_sale",
    ],
    "data": [
        "security/analitix_groups.xml",
        "security/ir.model.access.csv",
        "security/analitix_rules.xml",
        "data/analitix_params.xml",
        "data/analitix_cron.xml",
        "data/mail_data.xml",
        "views/analitix_store_views.xml",
        "views/analitix_door_views.xml",
        "views/analitix_device_views.xml",
        "views/analitix_event_views.xml",
        "views/analitix_staff_signature_views.xml",
        "views/analitix_job_views.xml",
        "views/analitix_audit_views.xml",
        "views/analitix_hourly_views.xml",
        "views/analitix_door_hourly_views.xml",
        "views/res_users_views.xml",
        "wizards/store_setup_views.xml",
        "views/analitix_menus.xml",
    ],
    "demo": [
        "demo/analitix_demo.xml",
    ],
    "images": [
        "static/description/banner.png",
    ],
    "price": 0.00,
    "currency": "USD",
    "installable": True,
    "application": True,
    "auto_install": False,
}
