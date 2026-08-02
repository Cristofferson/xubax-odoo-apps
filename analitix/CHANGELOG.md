# Changelog

All notable changes to Analitix. Versions follow Odoo's convention:
`19.0.<phase>.<minor>.<patch>`.

## 19.0.6.0.0 — Packaging, manuals and publication

* **Manuals inside the app**, in Spanish and English, chosen automatically from
  the user's own language: a user manual for the shop and an implementation
  guide for whoever mounts the cameras. Reachable from a Help menu inside
  Analitix rather than from a PDF nobody can find six months later.
* **Store page** (`static/description/index.html`) with the value proposition,
  the feature table by phase, hardware requirements and an FAQ.
* Icon and banner with the Analitix identity.
* `CHANGELOG.md` and a technical `README.md`.
* Verified that the published archive carries no `edge/` folder (the edge agent
  ships separately, with its own installer) and no computer-vision
  `external_dependencies` — the addon only ever receives JSON.

## 19.0.5.0.0 — The watch list

* `analitix.watch.person`: entries are **always** created by hand after a
  documented incident. No code path creates one.
* **Double control**: a draft entry matches nobody. A *second* authorised person
  activates it, and the person who added it cannot be the one who confirms.
* **Expiry and periodic review**, with a hard per-store ceiling. Lapsing is the
  default; staying on the list is what takes a deliberate act. An expired entry
  is not deleted — the record of why somebody was listed is part of the trail.
* A match is a prompt to pay attention: never an accusation, never an automatic
  action, never a screen, never the sales floor at large. It goes to a named,
  restricted group at a threshold far stricter than ordinary re-identification,
  and only for a reading the edge could vouch for as a live person.
* **False positives are recordable** — a list whose mistakes nobody writes down
  is a list nobody can fix.
* **Reads are audited**, not only writes.
* New `Security / Compliance` role, deliberately outside the commercial
  hierarchy and granted to nobody on install.
* Spanish translation completed: every string in the module.

## 19.0.4.0.0 — The action layer

* Signage rule engine that resolves *where* before *what*, so an offer lands on
  the screen the customer is standing near.
* Personal welcome with a social privacy rule: a known customer is named on a
  screen only when they arrived alone.
* Floor coaching measured against the alerts a salesperson **answered**.
* Visit frequency, CRM leads from lost sales, and staff attendance written into
  Odoo's own `hr.attendance`.
* Per-store subscription plan as a configuration control, never a licence check
  that could switch a paying shop's cameras off.
* Monthly value report in plain language, with every estimate labelled as one.

## 19.0.3.0.0 — Floor, lost sales and the discreet nudge

* Zones and displays; dwell, engagement and attention.
* Lost-sale detection: long dwell, unserved, and no ticket — all three.
* The discreet alert on five independent channels (Odoo app, Discuss, WhatsApp,
  audible chime, signage screen), routed by a per-zone, per-weekday, per-hour
  rota with a fallback, and recorded with response time and outcome.
* Display performance: attention beside the sales of what is actually on it.
* Ticket attribution, anonymous, falling back to the purchase unit.
* Optional customer identification, off by default and read-audited.
* Behaviour signals — anonymous, about patterns, never about people.

## 19.0.2.0.0 — Visits, demographics and purchase units

* Anonymous re-identification across every door, so one customer is one visit.
* Face signatures encrypted at rest and deleted on the store's own retention
  window, enforced by a scheduled job.
* Purchase units: people who cross a door together are one buying decision.
* Optional demographics with a confidence floor; low-confidence readings are
  kept and flagged rather than silently averaged in.
* Liveness plumbing.

## 19.0.1.0.0 — Counting, conversion and the ingest API

* Stores with any number of doors, defined in configuration and never in code.
* Hardened ingest API: one hashed API key per device, rotatable and revocable,
  scoped to its own store, HTTPS enforced, idempotent by client uuid.
* Device health with heartbeats and an offline alert; ingest-volume anomalies.
* Emergency capture kill switch per store.
* Staff exclusion by encrypted employee face signature.
* Hourly conversion analytics against POS: conversion rate, ATV, UPT, revenue
  per visitor, visitors per ticket, and density per square metre.
* Asynchronous job queue; separate technical and commercial dashboards.
