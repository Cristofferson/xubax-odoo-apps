# Analitix Ingest API — v1

The contract between an edge agent and Odoo. It is written so that a third
party integrating a different camera can build an agent without reading the
addon's source or guessing at behaviour.

Everything here is implemented in `controllers/api.py`.

---

## 1. Transport and authentication

| | |
|---|---|
| Base path | `/analitix/api/v1` |
| Transport | **HTTPS only.** A plaintext request is answered `403 tls_required`. |
| Auth header | `Authorization: Bearer <api_key>` |
| Fallback header | `X-Analitix-Key: <api_key>` — for CCTV firmware that cannot set `Authorization` |
| Content type | `application/json` |
| CSRF | Not applicable; these routes are exempt |

### The API key

* One key per device. Never shared across a fleet — a shared key cannot be
  revoked for one camera without killing every other.
* Format `alx_<43 url-safe characters>`.
* Shown **once**, when the device is created or its key is rotated. Odoo stores
  only a SHA-256 digest, so a lost key cannot be recovered — rotate instead.
* Scope: posting events for **its own store** and reading **its own**
  configuration. It is not a login. It reaches no business data and no other
  store.
* Revocation is instantaneous and requires no access to the hardware.

### Behind a reverse proxy

Odoo listens on plain HTTP behind nginx, so the TLS check reads
`X-Forwarded-Proto`. This is only safe because `proxy_mode = True` is set and
the proxy is the sole route in. A deployment that exposes Odoo directly must not
set `proxy_mode`.

For a lab bench without a certificate, set the system parameter
`analitix.allow_insecure_ingest = 1`. It ships as `0` on purpose: a deployment
that relaxes it is making a conscious, reversible choice rather than finding out
months later that a store has been posting in the clear.

---

## 2. `POST /analitix/api/v1/events`

Submit a batch of crossings.

### Request

```json
{
  "agent_version": "1.0.0",
  "queue_size": 12,
  "events": [
    {
      "uuid": "0f3c8a2e-4b1d-4a5e-9f7a-2c1b8d6e4f10",
      "ts": "2026-08-01T14:32:05-06:00",
      "direction": "in",
      "count": 1,
      "track": "t-8841",
      "is_staff": false,
      "embedding": "base64-or-json-array",
      "embedding_model": "buffalo_l"
    }
  ]
}
```

#### Envelope

| Field | Type | Required | Meaning |
|---|---|---|---|
| `events` | array | yes | Up to **1000** per request. Larger is `413`. |
| `agent_version` | string | no | Recorded on the device; useful when diagnosing a bad rollout. |
| `queue_size` | int | no | Events still buffered locally. A number that keeps climbing is the early warning that a store is about to lose data. |

#### Event

| Field | Type | Required | Meaning |
|---|---|---|---|
| `uuid` | string | **yes** | Unique per crossing, generated **before** the first send attempt. Without it the event is rejected — see §3. |
| `ts` | ISO-8601 | **yes** | When the crossing happened **at the store**. With or without an offset; naive is read as UTC. |
| `direction` | `in` \| `out` | no | Default `in`. |
| `count` | int ≥ 1 | no | Default 1. Use it when a sensor reports groups. |
| `track` | string | no | The tracker id the agent used while the person was in frame. Phase 2 ties it to a visitor. |
| `is_staff` | bool | no | The agent already matched an employee locally. Trusted — the agent holds the same signatures Odoo gave it. |
| `staff_score` | float | no | Similarity behind `is_staff`, kept so thresholds can be tuned against real data. |
| `employee_ref` | string | no | `hr.employee.barcode` of the matched employee. |
| `embedding` | array\|base64 | no | Face vector for **server-side** matching when the agent cannot match locally. Either a JSON array of floats or base64 little-endian float32. |
| `embedding_model` | string | no | Default `buffalo_l`. Vectors from different models are never compared. |
| `liveness` | float 0-1 | no | Edge confidence that a live person crossed rather than a photograph held to the camera. Stores that set *Require Liveness* discard readings below their floor — **the crossing still counts**, only the face is not trusted with a decision. |
| `demographics` | object | no | Age, gender and expression estimate. See below. |

#### `demographics`

```json
{"age": 31, "age_confidence": 0.91,
 "gender": "female", "gender_confidence": 0.88,
 "emotion": "neutral", "emotion_confidence": 0.62}
```

| Field | Meaning |
|---|---|
| `age` | Estimated age. Odoo stores the **band** it falls in, never the number — reporting a model's estimate to the year would present a guess as a measurement. Send `age_band` directly if the edge already banded it. |
| `gender` | `female`, `male` or `unknown`. An estimate of presented appearance, not a statement about anyone's identity; `unknown` is a legitimate and common answer. |
| `emotion` | `neutral`, `happy`, `sad`, `angry`, `surprised`, `fearful`, `disgusted`. |
| `*_confidence` | 0-1. Readings below the store's floor are **stored and flagged unreliable**, not dropped, so a dashboard can exclude them explicitly instead of averaging a coin flip into the customer's numbers. |

Ignored entirely unless the store has *Capture Demographics* switched on. It is
off by default: it needs a second, front-facing camera per door, and a store
without one should not see empty charts suggesting the system is broken.

> **`ts` is the store's clock, not Odoo's.** After an outage an agent replays
> hours of buffered events; they must land on the hour they actually happened.
> An event whose timestamp cannot be parsed is rejected rather than stamped
> "now" — silently piling an outage onto the recovery minute would turn a
> visible gap into an invisible lie.

### Response `200`

```json
{
  "ok": true,
  "stored": 2,
  "duplicates": 1,
  "rejected": [{"index": 3, "reason": "bad_timestamp"}],
  "acknowledged": ["uuid-a", "uuid-b", "uuid-c"]
}
```

| Field | Meaning |
|---|---|
| `stored` | Newly written. |
| `duplicates` | Already held. **Success, not failure** — see §3. |
| `rejected` | Per-event `{index, reason}`. One bad row never rejects the batch. |
| `acknowledged` | Every uuid Odoo now holds, stored **and** duplicate. **The agent deletes exactly these from its local buffer and nothing else.** |

Rejection reasons: `not_an_object`, `missing_uuid`, `bad_direction`,
`bad_timestamp`, `bad_count`.

### Errors

| Status | `error` | What the agent should do |
|---|---|---|
| `400` | `bad_json` | Bug in the agent. Log; do not retry unchanged. |
| `400` | `events_must_be_a_list` | Same. |
| `401` | `invalid_credentials` | Key is unknown, revoked, or the device is archived. Stop, keep buffering, alert. |
| `403` | `tls_required` | Plain HTTP. Fix the endpoint URL. |
| `413` | `batch_too_large` | Split and resend. |
| `423` | `capture_paused` | The store's kill switch is on. **Keep counting and buffering**; retry after `retry_after_s` (default 300). |

A `401` is deliberately identical for an unknown key, a revoked key and an
archived device. Distinguishing them would let an attacker map which device UIDs
exist.

---

## 3. Idempotency — the contract that makes retries safe

A store's internet is not reliable, and an agent that gives up on an unanswered
request loses real customers from the count. So the agent retries. Which means
Odoo **will** see the same crossing more than once, and must count it once.

The rules:

1. The agent generates `uuid` **before its first send attempt** and keeps it
   across retries, restarts and reboots. Generating a fresh uuid per attempt
   defeats the entire mechanism.
2. Odoo enforces uniqueness with a database constraint, not application logic.
3. A repeat is reported in `duplicates` and listed in `acknowledged`.
4. The agent clears from its buffer exactly what is in `acknowledged`.

Point 3 is what stops an infinite loop. Silently dropping a duplicate would
leave the agent believing the event never arrived, and it would resend it
forever.

The same uuid appearing twice **inside one batch** is also collapsed.

---

## 4. `POST /analitix/api/v1/dwell`

How long tracked people have spent in zones and at displays.

```json
{
  "dwells": [
    {"track": "t-8841", "zone": "R",  "since": "2026-08-01T14:32:05-06:00",
     "seconds": 214, "served": false},
    {"track": "t-8841", "poi": "SC1", "since": "2026-08-01T14:33:10-06:00",
     "seconds": 46}
  ]
}
```

| Field | Meaning |
|---|---|
| `track` | The tracker id the agent gave this person **at the door**. Odoo resolves it to a visit; an unknown track is skipped quietly, because someone who walked in before the agent restarted has no visit to attach to and that is not an error. |
| `zone` / `poi` | The zone's or display's *Reference* as configured in Odoo. Send one or the other, not both. |
| `since` | When they arrived at it. Together with the track and the zone this is the upsert key. |
| `seconds` | Time there **so far**. |
| `served` | A salesperson is with them. Suppresses the lost-sale nudge. |

> **Send a running total, not a final one.** Report while the person is still
> standing there and keep updating the same observation. A lost-sale nudge that
> arrives after the customer has walked out is worthless, and Odoo upserts on
> `(visit, zone, since)` so repeating the observation with a bigger number
> updates one row instead of creating a dozen — and raising a dozen alerts.

Evaluated **inline**, unlike everything else in this API: this is the one thing
that is worthless late. What it can trigger — the alert, WhatsApp — is already
non-blocking.

```json
{"ok": true, "stored": 2, "skipped": 0}
```

---

## 5. `POST /analitix/api/v1/checkout`

Attribute a ticket to the visit that produced it.

```json
{"pos_reference": "Order 00042-001-0003",
 "embedding": "base64-or-json-array"}
```

The comparison is queued, so nothing here can make a cashier wait while a
customer stands at the counter. A ticket that has not synced to Odoo yet is
answered `{"ok": true, "queued": false}` — not an error to retry against, since
the purchase-unit fallback already attributes it.

A store with no till camera still gets group-level attribution: the ticket
attaches to the purchase unit frozen at the door.

---

## 6. `POST /analitix/api/v1/heartbeat`

```json
{"agent_version": "1.0.0", "queue_size": 0}
```

```json
{
  "ok": true,
  "server_time": "2026-08-01T20:32:05Z",
  "heartbeat_interval_s": 60,
  "capture_enabled": true
}
```

The agent adopts `heartbeat_interval_s` from every reply, so retuning a whole
fleet is a field change in Odoo rather than a visit to each store.

Missing heartbeats are what raise the alarm: nothing will ever arrive to
announce that a camera died, so Odoo polls for the absence. Per store,
`Degraded After` and `Offline After` decide when. A *critical* device going
offline raises an Odoo activity and e-mails the store's technical contacts,
because while it is down that store's conversion figures are incomplete and the
customer is paying for data nobody is capturing.

---

## 7. `GET /analitix/api/v1/config`

Everything the agent needs, resolved server-side:

```json
{
  "ok": true,
  "device": {"uid": "mor01-north-counter", "name": "North counter",
             "role": "door_counter", "hardware": "depth_cam",
             "config": {"line": [[0, 540], [1920, 540]], "camera": 0}},
  "door":   {"id": 7, "name": "North Entrance", "counts_visitors": true},
  "store":  {"id": 3, "name": "Anello Morelia", "tz": "America/Mexico_City",
             "capture_enabled": true, "exclude_staff": true,
             "staff_match_threshold": 0.55, "heartbeat_interval_s": 60}
}
```

`device.config` is free-form JSON held on the device record — line coordinates,
camera index, zone polygons. It is there so an implementer can retune a camera
from Odoo instead of going back to the store with a laptop.

Poll it on start-up and periodically (hourly is plenty).

---

## 8. `GET /analitix/api/v1/staff_signatures`

```json
{
  "ok": true,
  "enabled": true,
  "threshold": 0.55,
  "signatures": [
    {"id": 12, "employee_ref": "EMP-004", "model": "buffalo_l",
     "vector": [0.013, -0.221, "…512 floats"]}
  ]
}
```

Only the calling device's own store. Every call is written to the audit log.

**Prefer edge-side matching.** With the signatures held locally the agent
decides in-process, the crossing arrives already labelled `is_staff`, and no
face vector ever crosses the network. Server-side matching exists for thin
agents that cannot hold the set; it is a fallback, not the design.

Refresh on start-up and hourly. A newly enrolled employee is excluded from the
count from the next refresh onward.

---

## 9. What happens to a crossing after it is stored

1. **Staff check.** If the crossing matches an enrolled employee it is kept but
   flagged `counted = false`, and it never becomes a visit.
2. **Visit resolution** (queued, never on the request). The face is matched
   against the store's *live* signatures — those seen inside the retention
   window, never the store's whole history and never another store's. A match
   continues the existing visit; no match mints a new anonymous handle.
3. **Purchase unit.** People crossing the *same door* within the store's
   *Together Within* window become one buying decision. The decision is frozen
   at the door and never revisited: a store that counts a family of four as
   four visitors and one ticket reads a 25% conversion rate when the truth was
   100%.
4. **Retention.** A scheduled job deletes expired signatures. The visit
   survives; the route back to a face does not.

Nothing in steps 2-4 is required for a crossing to be counted. A face that is
turned away, badly lit or absent costs you the visit-level detail and nothing
else — the visitor total, and therefore the conversion rate, is never at the
mercy of a readable face.

---

## 10. What the API deliberately does not accept

**No images. No video. Ever.** Not as a field, not as an attachment, not
"temporarily for debugging". The edge extracts an embedding — a vector of
numbers from which no face can be reconstructed — and discards the frame in
memory. There is no endpoint that would accept a picture, which is the only
version of that promise a customer can actually verify.

Embeddings that do reach Odoo are encrypted at rest, and the ones parked on an
event are wiped as soon as the matching job has run.

---

## 11. Alert channels

Alerts are raised inside Odoo, not through this API, but an integrator should
know what a store can switch on:

| Channel | Discreet? | Notes |
|---|---|---|
| Odoo mobile app | yes | `bus.bus` push plus an activity. Default. |
| Odoo chat (Discuss) | yes | One-to-one message. Odoo's client chimes for it on the salesperson's own device. |
| WhatsApp | yes | Needs Odoo's `whatsapp` module; detected at runtime. |
| Audible chime | **no** | The customer may hear it if the phone is not on silent. |
| Signage screen | **no** | The customer reads whatever appears there. Needs the Xibo connector and a display group on the zone. |

The last two are off by default. Each alert records which channels actually
delivered it, so a delivery report never claims more than happened.

---

## 12. Reference agent

`edge/analitix_agent.py` in this repository implements this contract end to end:
persistent uuids, an encrypted on-disk buffer that survives an outage, ordered
replay, heartbeats, config and signature refresh, and local staff matching.

Read it before writing your own — every rule above exists because getting it
wrong corrupts a paying customer's numbers in a way that is very hard to notice
afterwards.
