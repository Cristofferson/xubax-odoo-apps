# Changelog

All notable changes to Analitix. Versions follow Odoo's convention:
`19.0.<phase>.<minor>.<patch>`.

## 19.0.7.2.0 — Listing regenerated, and a figure that was wrong on screen

* **Screenshots and screencasts regenerated** against the current product. The
  ones on the listing predated phases 5 and 7, so the page showed neither the
  watch list nor the chain console and its store form was two rounds of
  permission changes out of date. A sixth screencast covers the console and the
  two elevated decisions.
* **The store page now describes what the product actually is**: sections on
  the watch list and on chain scale, phase 7 in the feature table, and an FAQ
  entry for the shop that will never own a second branch.
* **Ratios were summed instead of averaged.** Grouping the chain console by
  region reported a conversion rate of **750%**. The hourly views have declared
  `aggregator="avg"` since phase 1; the phase 7 models forgot — and the check
  written to catch that found four more in the monthly value report and two in
  the hourly dashboard, all shipping since their own phase.
  `tests/test_screens.py` now asserts the rule for every ratio in the addon.
* In the demo database the administrator also gets the corporate role, so a
  reviewer can find the chain console at all. A real installation still grants
  it to nobody.
* Unused screenshots dropped from the package.

## 19.0.7.1.0 — What the end-to-end run found

An end-to-end suite was added (`tools/e2e/`) that drives the product the way a
customer does: over HTTP, with the real edge agent as a subprocess, and through
a real browser. It found five defects that 263 in-process tests could not see,
because those run in the same process as the server, without a browser, as a
user far more privileged than any customer's.

**Fixed**

* **The store form was unusable for the role it was built for.** An Analitix
  Manager who was not also a Point of Sale user got an Access Error opening
  their own store: the form shows `register_ids`, and reading `pos.config`
  needs the POS group. The same trap applied to staff enrolment
  (`hr.employee`), ticket attribution (`pos.order`), the subscription
  (`sale.order`) and leads from lost sales (`crm.lead`). Read-only access is
  now granted to the narrowest Analitix group that can reach each screen.
* **The emergency kill switch could be blocked by a validation rule.**
  `register_ids` was required whenever sales matched by register, so a store
  with no register mapped yet could not be saved — and *Pause Capture* saves
  the form first. An emergency control a half-finished configuration can block
  is not an emergency control. The field is no longer required; an unmapped
  store gets a plain warning instead.
* **A computed count inherited another model's access rules.** The store
  counters shared one method, so counting registers — which nobody on the floor
  is shown — made the store kanban fail for a salesperson.
* **The chain console crashed for everybody.** Its default filter used
  `date.replace(day=1)`, which the client evaluates in JavaScript and does not
  implement.
* Configuration tabs, biometric handles and the subscription are now restricted
  to the roles that own them rather than merely hidden.

**Added**

* `tests/test_screens.py` — opens every action as every role, with only that
  role's rights, and resolves the comodel behind every relational field on the
  view. The regression guard for the whole class of bug above.
* `tools/e2e/` — the API contract, the real agent (including an outage and its
  recovery), and six browser journeys. 61 checks.

## 19.0.7.0.0 — Chain scale (optional)

Everything before this works for one shop and needs none of it.

* **Chains and regions.** `analitix.brand` → `analitix.region` →
  `analitix.store`, with no fixed limit on branches. A single-store customer
  creates neither and nothing about their installation changes.
* **Hierarchical scope.** A regional manager is given a *region*, which already
  includes the branches that open next year — a hand-written list of stores is
  one nobody remembers to extend, and stale access outlives the person it was
  written for. Stores and regions resolve into one effective scope that the
  record rules read, so the two can never disagree.
* **New roles**: Regional Manager (compares their region, configures nothing)
  and Corporate / Head Office (the whole chain, plus the elevated decisions).
* **The corporate console.** Every branch on the same yardstick, and each one
  measured against its own region on the same day — which removes the week, the
  weather and the season, and leaves what is particular to that shop.
* **Two elevated decisions**, guarded in code rather than only in the UI, and
  both audited: whether recognition correlates a person across branches (off by
  default) and whether the watch list is shared between them (on by default).
* **Daily rollup and safe pruning.** One row per store per day is what every
  long-horizon report reads, so crossing events become deletable on the
  customer's own policy without losing a reported figure. Pruning refuses to
  run ahead of the summary, and the two retention mechanisms that used to
  exist are now one.
* Face matching is always bounded by store — or by one chain, never by the
  whole database.

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
