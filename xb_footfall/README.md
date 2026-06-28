# xb_footfall — Footfall Analytics (People Counting)

Count store visitors from **any** sensor and cross them with POS sales to get
the **conversion KPI** (`tickets / visitors`), inside Odoo 19.

## How it works

```
sensor/edge ──HTTPS+Bearer──► /xb_footfall/ingest ──► xb.footfall.event
                                                          │
                                  xb.footfall.hourly (SQL view) ◄── pos_order
                                                          │
                                              Dashboard (graph/pivot)
```

Every source — Hikvision/Dahua native People Counting, a DIY edge mini-PC
(YOLO + ByteTrack virtual line), or an IR beam — posts the **same payload**.
Odoo never receives an image, only the count (privacy by design / LFPDPPP).

## Models
- `xb.footfall.device` — one per sensor; holds the Bearer token (`Configuration ▸ Devices`).
- `xb.footfall.event` — raw crossing events (in/out, count).
- `xb.footfall.hourly` — read-only PostgreSQL view: visitors LEFT-JOIN POS per
  company per hour → `conversion_rate`. Always live, no cron.

## Ingest API
```
POST /xb_footfall/ingest
Authorization: Bearer <device access_token>
Content-Type: application/json

{
  "device_uid": "anello-morelia-puerta1",
  "events": [
    {"ts": "2026-06-28T14:32:05-06:00", "direction": "in",  "count": 1},
    {"ts": "2026-06-28T14:32:09-06:00", "direction": "out", "count": 1}
  ]
}
```
Response: `{"ok": true, "stored": 2}`. Send a `seq` per event to dedupe retries.

Get the token: open the device → **Regenerate Token** (shown once in a toast).

## Quick test (curl)
```bash
TOKEN=...     # from the device form
curl -sk -X POST https://<cliente>.diamane.mx/xb_footfall/ingest \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"events":[{"direction":"in","count":1}]}'
```

## Roadmap (not in this scaffold)
- Dedupe by `(device_id, seq)` constraint + idempotent ingest.
- Recurring subscription line "Footfall Analytics" per store (clone the
  `_sync_mcp_subscription_line` pattern).
- Dwell time / zones / heatmap fields (camera CV).
- Push the KPI to Xibo screens / the self-service videowall.
- Token hashing at rest + per-IP rate limit on the controller.

See `examples/edge_poster.py` for a reference edge sender.
