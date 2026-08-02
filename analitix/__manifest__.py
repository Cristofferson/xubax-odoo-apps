# -*- coding: utf-8 -*-
{
    "name": "Analitix — Physical Store Intelligence",
    "version": "19.0.4.0.0",
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

Phase 2
-------

* **Visits, not just crossings.** The same anonymous face is recognised across
  a visit, so a customer who steps out for a phone call and comes back counts
  once. Counting them three times would report a conversion rate a third of
  the truth.
* **Re-identification across every door** the store has, and only where there
  is more than one door to correlate. Matching never crosses store boundaries.
* **Short-lived by design.** Face signatures are anonymous, encrypted at rest
  and deleted on a retention window the store sets. No name, no image, and a
  scheduled job that enforces it.
* **Purchase units.** People who cross the same door together are one buying
  decision, frozen at the door and never revisited. A store that counts a
  family of four as four visitors and one ticket reads a 25% conversion rate
  when the real figure was 100%.
* **Demographics** (optional, off by default): coarse age band, presented
  gender and expression, with a confidence floor. Low-confidence readings are
  kept and flagged rather than silently averaged into the customer's numbers.
* **Liveness plumbing** so later phases can refuse a reading that may have come
  from a photograph.

Phase 3
-------

* **Zones and displays.** Divide the floor into as many zones as the shop
  actually has, and mark the displays inside them. "Twelve minutes inside"
  tells an owner nothing; "eleven of those twelve at the ring counter, and
  nobody spoke to them" tells them exactly where the money went.
* **Lost sales.** Long dwell, unserved, and no ticket — all three, because each
  alone is ordinary. This is the number that sells the product.
* **The nudge, on the channels the shop chooses.** Three discreet ones that
  only the assigned salesperson perceives — the Odoo mobile app, Odoo's
  internal chat (Discuss), and WhatsApp — plus two that the customer may
  notice, an audible chime and a message on the signage screen. The last two
  are off by default and each says in its own help text exactly what it costs
  in discretion. Routed by a per-zone, per-weekday, per-hour rota, escalated to
  a fallback when nobody is covering, and recorded with the response time and
  the channels that actually delivered.
* **Display performance.** Attention beside the sales of the products actually
  on each display, surfacing the two findings worth acting on: draws a crowd
  and sells little, or sells well from a cold corner.
* **Ticket attribution.** Which visit produced which ticket, anonymously,
  falling back to the purchase unit where there is no till camera.
* **Optional customer identification.** When a customer hands over their
  details at the till, their signature can become a named one so the shop
  greets them properly next time. Off by default, guarded by liveness, and
  every later read of that list is audited.
* **Behaviour signals.** In and out repeatedly, a long unattended stop, a group
  that scatters. Anonymous and about patterns, never about people — the named
  watch list is a separate phase with separate controls.

Phase 4
-------

* **The screens react, and to the right screen.** A configurable rule engine
  resolves *where* before *what*: a bundle offer belongs on the screen the
  group is standing near, not on the one by the door. Triggers ship for
  walk-outs, groups, profiles, quiet hours and known customers, and every shop
  edits its own without calling anybody.
* **Personal welcome, with a social rule.** A recognised customer is greeted by
  name, with context assembled from CRM, their POS history and the special
  dates addon. Only when they arrived alone: naming somebody on a screen in
  front of the person they came with tells that person something about them.
  With company, the screen stays neutral and the greeting goes to the
  salesperson.
* **Floor coaching.** Per salesperson: alerts received, response time, and how
  many of the ones they answered ended in a sale — measured against what they
  answered, so nobody is marked down for a nudge that arrived mid-customer.
* **Visit frequency**, **CRM leads from lost sales**, and **staff attendance**
  written into Odoo's own hr.attendance, never overwriting a manual correction.
* **Subscription per store**: a plan that governs what the customer's users can
  switch on — a configuration control, never a licence check that could turn a
  paying shop's cameras off over a billing hiccup.
* **The monthly value report**: plain language, e-mailed to the owner. Visitors,
  conversion, walk-outs spotted and rescued, and roughly what that was worth —
  labelled an estimate every time, because inflating it is the fastest way to
  lose the customer who eventually checks.

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
        # Named by the brief: staff attendance feeds Odoo's own hr.attendance
        # rather than a parallel table only this addon understands. Community,
        # so it costs the customer nothing.
        "hr_attendance",
        "point_of_sale",
        # sale.order is Community and is what an Odoo 17+ subscription IS: the
        # recurring machinery is Enterprise, but the link works everywhere and
        # the recurring fields are read defensively.
        "sale",
        # Named by the project brief as a module to integrate with rather than
        # rebuild: a lost sale can open a lead. Community, so it costs the
        # customer nothing. Odoo's WhatsApp module is deliberately NOT here —
        # it is Enterprise, and half the market for this app does not have it.
        "crm",
    ],
    "data": [
        "security/analitix_groups.xml",
        "security/ir.model.access.csv",
        "security/analitix_rules.xml",
        "data/analitix_params.xml",
        "data/analitix_sequence.xml",
        "data/analitix_cron.xml",
        "data/mail_data.xml",
        "views/analitix_store_views.xml",
        "views/analitix_door_views.xml",
        "views/analitix_device_views.xml",
        "views/analitix_event_views.xml",
        "views/analitix_staff_signature_views.xml",
        "views/analitix_visitor_views.xml",
        "views/analitix_zone_views.xml",
        "views/analitix_poi_views.xml",
        "views/analitix_alert_views.xml",
        "views/analitix_lost_sale_views.xml",
        "views/analitix_signage_views.xml",
        "views/analitix_value_views.xml",
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
