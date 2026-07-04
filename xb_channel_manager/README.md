# Hotel OTA Channel Manager (`xb_channel_manager`)

Connects the Odoo 19 Hotel/Rental booking flow with OTA platforms.

## Drivers

| Driver | Platforms | Direction | Requirements |
|---|---|---|---|
| **iCal** | Airbnb, Booking.com, Vrbo, any iCal-capable OTA | Export busy dates / import reservations & blocks | None — works out of the box |
| **Channex** | Booking.com, Expedia, Airbnb, Agoda, 100+ | Push availability + nightly rates / bookings feed + webhooks | Channex.io account (free sandbox: `https://staging.channex.io`) |

## Architecture

- `xb.cm.channel` — one record per connected platform; policies
  (auto-import, draft/confirm, cancellation), credentials, sync state.
- `xb.cm.listing` — maps an Odoo rental `product.template` (room type)
  to the external listing; holds the secret iCal export token and the
  Channex room-type/rate-plan ids.
- `xb.cm.reservation` — staging inbox; every OTA reservation lands here
  first, then becomes a rental `sale.order` (policy-driven).
- `xb.cm.engine` — availability & booking service. Detects the **Hotel
  industry** at runtime (`x_availability` + `planning.slot` +
  `x_resource_ids`): assigns a free physical room per import and runs
  the native availability recompute. Falls back to plain-Rental
  occupancy counting (capacity per listing) otherwise.
- `xb.cm.log` — sync log with auto-vacuum (30 days).

HTTP endpoints (`auth=public`, token-gated):
- `GET /cm/ical/<token>.ics` — per-listing busy-dates feed.
- `POST /cm/channex/webhook/<token>` — Channex booking notifications.

Cron: one sync worker every 10 minutes (per-channel interval throttle).

## Tests

`odoo-bin -d <db> -i xb_channel_manager --test-enable --test-tags /xb_channel_manager`

15 tests: iCal parser/generator (Airbnb + Booking fixtures, folding,
escaping, garbage), staging idempotency, order creation (price honoured,
draft/confirm policies), overbooking guard, full-dates export,
auto-cancellation, blocks, Channex payload mapping + cancellation.

Verified end-to-end on a Hotel-industry database: real HTTP feed import
→ confirmed order, automatic room assignment, `x_booked` decrement,
cancellation frees the room; Channex webhook over HTTP → order with the
exact OTA amount.

## Setup (iCal / Airbnb example)

1. Channel Manager ▸ Channels ▸ New: type *iCal*, platform *Airbnb*.
2. Add a room mapping: pick the room-type product.
3. Copy the **Export URL** into Airbnb ▸ Calendar ▸ Import calendar.
4. Paste the Airbnb **calendar export link** into *Import URL*.
5. Click *Connect*. Done — sync runs every 10 minutes.
