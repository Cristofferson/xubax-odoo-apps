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
  models/        store, door, device, event, staff signatures, job queue, audit
  controllers/   the v1 ingest API — the only way in from outside Odoo
  wizards/       new-store setup: N doors and their API keys in one screen
  security/      groups, ACLs, and the record rules that isolate tenants
  tests/         configurability, ingest, security, isolation, health, analytics
  doc/API.md     the ingest contract, for anyone writing their own agent
  edge/          the reference camera agent — NOT part of the published addon
```

`edge/` ships with the repository and is deliberately excluded from the
apps.odoo.com zip. The addon has **no** computer-vision dependency: it receives
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
| 1 | Counting, conversion, doors, devices, staff exclusion | **This release** |
| 2 | Demographics, purchase unit, anonymous re-identification | Planned |
| 3 | Zones, lost sales, POI attention, face↔ticket↔partner | Planned |
| 4 | Xibo triggers, CRM, loyalty, attendance, subscription, ROI report | Planned |
| 5 | Watch list | Planned |
| 6 | Packaging, manuals, videos, apps.odoo.com | Planned |
| 7 | Chain scale, role hierarchy, HQ console | Optional |

Each phase leaves the addon installable and useful on its own, because each is
sold on its own.

---

© XUBAX — https://www.xubax.com — OPL-1
