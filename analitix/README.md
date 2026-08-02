# Analitix — Physical Store Intelligence

Store intelligence on Odoo 19: visitor counting across any number of doors,
conversion against POS, staff exclusion, device health, and a hardened ingest
API for edge cameras.

Not a people counter. The counter is the foundation; the product is what the
owner does with the number.

---

## The rule this codebase is built around

> **Is this different for each customer store? Then it is configuration, not
> code.**

Analitix is sold to many stores, not built for one. Nothing that varies between
customers may be a constant in the source: the number of doors, the number of
zones and cameras, the thresholds, the alert recipients. All of it lives on
`analitix.store` and its children, and `tests/test_configurability.py` exists to
fail if anyone forgets — it proves a one-door boutique and a seven-door mall
unit both work through the same code.

## Repository layout

```
analitix/
  models/        store, door, device, event, visits, signatures, demographics,
                 purchase units, zones, displays, lost sales, alerts,
                 ticket attribution, behaviour signals, job queue, audit
  controllers/   the v1 ingest API — the only way in from outside Odoo
  wizards/       new-store setup: N doors and their API keys in one screen
  security/      groups, ACLs, and the record rules that isolate tenants
  tests/         configurability, ingest, security, isolation, health, analytics,
                 visits, floor, action, watch list, manuals
  static/manual/ the user manual and implementation guide, es + en
  static/description/  store page, screenshots and screencasts
  doc/API.md     the ingest contract, for anyone writing their own agent
  edge/          the reference camera agent — NOT part of the published addon
  tools/         packaging and translation generators — NOT part of the addon
```

`edge/` and `tools/` ship with the repository and are deliberately excluded from
the apps.odoo.com archive. `tools/package.sh` builds that archive and *asserts*
the exclusions rather than trusting them. The addon has **no** computer-vision dependency: it receives
JSON and nothing else. That is what keeps `insightface` and `torch` out of the
customer's Odoo server.

## Architecture

```
   store                        network                    Odoo
┌───────────┐               ┌─────────────┐         ┌────────────────┐
│  camera   │  frames       │             │  JSON   │ analitix.event │
│     ↓     │  (in memory,  │   HTTPS     │ ──────► │       ↓        │
│ edge agent│   discarded)  │  Bearer key │  uuid   │ hourly views   │
│     ↓     │ ────────────► │             │ deduped │       ↓        │
│ encrypted │               └─────────────┘         │  dashboards    │
│  queue    │                                       └────────────────┘
└───────────┘
```

Frames never leave the mini-PC. There is no endpoint that would accept one,
which is the only version of that promise a customer can verify rather than
take on trust.

## Running the tests

```bash
odoo-bin -d <db> -u analitix --test-enable --test-tags=/analitix \
         --stop-after-init --workers=0
```

The suite covers, in order of how much it would cost to get wrong:

| File | Guards |
|---|---|
| `test_isolation.py` | Two customers on one instance see zero of each other's data |
| `test_security.py` | Key hashing, rotation, revocation, TLS, kill switch, encryption |
| `test_ingest.py` | Idempotency, partial success, edge timestamps |
| `test_configurability.py` | 1 door and 7 doors, per-store thresholds |
| `test_health.py` | Offline detection, alerting, the job queue, anomalies |
| `test_analytics.py` | Every conversion ratio, against hand-computed values |
| `test_visits.py` | Re-identification, visit boundaries, retention, purchase units |
| `test_floor.py` | Alert routing and discretion, lost sales, identification, behaviour |
| `test_action.py` | Screen routing, the social privacy rule, attendance, billing, ROI |
| `test_watchlist.py` | Manual-only entry, double control, expiry, what a match must NOT do |
| `test_manual.py` | The in-app manuals resolve, in the reader's own language |
| `test_chain.py` | Regional scope, the elevated decisions, the console, safe pruning |

## Building the published archive

```bash
tools/package.sh /tmp        # writes analitix-<version>.zip and checks it
```

It fails loudly if the edge agent, the build tooling or compiled Python made it
into the archive, if a required file is missing, or if the manifest ever
declares a computer-vision dependency.

## Documentation

The manuals live in the product, not in a PDF somebody e-mailed during the
rollout: **Analitix → Help**. Each is written separately in Spanish and English
rather than machine-translated, and the controller picks the reader's language.
They are plain static files under `static/manual/`, so they carry no dependency
on Odoo's asset bundle and add nothing to the translation catalogue.

Screenshots and screencasts under `static/description/` are captured from the
real UI over the module's own demo data, so they can be regenerated whenever the
product moves rather than drifting quietly out of date.

## Deploying an edge device

1. In Odoo: **Analitix → Configuration → New Store Setup**. Add one row per
   entrance. Copy the API keys off the last screen — they are shown once and
   Odoo keeps only their hashes.
2. On the mini-PC: install `edge/analitix_agent.py`, copy
   `edge/config.example.yaml` to `/etc/analitix/agent.yaml`, paste the URL and
   key, install `edge/analitix-agent.service`.
3. Verify: the device turns **Online** in Odoo within one heartbeat.

Use `source: demo` to prove the link to Odoo works before the hardware is
mounted.

## Phase status

| Phase | Scope | State |
|---|---|---|
| 1 | Counting, conversion, doors, devices, staff exclusion | **Done** |
| 2 | Visits, anonymous re-identification, demographics, purchase units | **Done** |
| 3 | Zones, lost sales, display attention, face↔ticket↔partner, alerts on five channels | **Done** |
| 4 | Signage routing, welcome context, coaching, attendance, subscription, ROI report | **Done** |
| 5 | Watch list | **Done** |
| 6 | Packaging, manuals, videos, apps.odoo.com | **Done** |
| 7 | Chain scale, role hierarchy, HQ console | **Done** (optional to sell) |

Each phase leaves the addon installable and useful on its own, because each is
sold on its own.

---

© XUBAX — https://www.xubax.com — OPL-1
