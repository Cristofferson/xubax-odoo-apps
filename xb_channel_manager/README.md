# Hotel OTA Channel Manager (`xb_channel_manager`)

Connects Odoo 18.0 (Community or Enterprise — only `sale` is required) with OTA
platforms. Every stay is a sale order line with `cm_checkin` / `cm_checkout`;
front-desk sales with those dates occupy the room on the channels too.

## Drivers

| Driver | Platforms | Direction | Requirements |
|---|---|---|---|
| **iCal** | Airbnb, Booking.com, Vrbo, any iCal-capable OTA | Export busy dates / import reservations & blocks | None — works out of the box |
| **Channex** | Booking.com, Expedia, Airbnb, Agoda, 100+ | Push availability + nightly rates / bookings feed + webhooks | Channex.io account (free sandbox: `https://staging.channex.io`) |

## Architecture

- `xb.cm.channel` — one record per connected platform; policies
  (auto-import, draft/confirm, cancellation), credentials, sync state.
- `xb.cm.listing` — maps an Odoo `product.template` (room type)
  to the external listing; holds the secret iCal export token and the
  Channex room-type/rate-plan ids.
- `xb.cm.reservation` — staging inbox; every OTA reservation lands here
  first, then becomes a `sale.order` (policy-driven).
- `xb.cm.engine` — availability & booking service. Detects the **Hotel
  industry** at runtime (`x_availability` + `planning.slot` +
  `x_resource_ids`): assigns a free physical room per import and runs
  the native availability recompute (with the Rental bridge). Otherwise
  occupancy is counted from confirmed stay lines (capacity per listing).
  Stay handling goes through the `_stay_*` hooks, overridden by the bridge.
- `xb.cm.season` — date rules per channel: nightly price (fixed or %),
  minimum stay, closed to arrival, stop sell, weekdays, rooms, priority.
- `xb.cm.rate.plan` — several Channex rate plans per room, each with a
  % / amount adjustment and its own minimum stay.
- `xb.cm.log` — sync log with auto-vacuum (30 days).

Money: reservations keep the OTA currency (inactive currencies are
activated) and the order uses a pricelist in that currency; the platform
commission (`ota_commission`, or the channel default %) is stored on the
reservation and the order (gross / commission / net). Rates are converted
to the channel currency and sent as decimal strings.

Modifications: a new revision of an imported booking updates the order
(dates, room type, price, room re-assignment) after an availability check
that ignores the order's own nights; policy *manual* only flags it.

HTTP endpoints (`auth=public`, token-gated):
- `GET /cm/ical/<token>.ics` — per-listing busy-dates feed.
- `POST /cm/channex/webhook/<token>` — Channex booking notifications.

Cron: one sync worker every 10 minutes (per-channel interval throttle).

## Tests

`odoo-bin -d <db> -i xb_channel_manager --test-enable --test-tags /xb_channel_manager`

Tests (Community, no Rental): currencies, commission (reported, default %, multi-room
split), modifications (auto, conflict, manual, iCal date change, contact
data kept), seasons + weekdays + rate plans + currency conversion,
revisions feed with acknowledge, ARI push; and iCal parser/generator (Airbnb + Booking fixtures, folding,
escaping, garbage), staging idempotency, order creation (price honoured,
draft/confirm policies), overbooking guard, full-dates export,
auto-cancellation, blocks, Channex payload mapping + cancellation,
secondary company, zero OTA commission, API key access, front-desk orders
blocking the room, seasonal pricing of unpriced stays, HTML chatter notes,
property timezone.

Verified against a live Channex staging property (rates, seasons,
minimum stay, availability; booking new / modified / cancelled through the
webhook). Verified end-to-end on a Hotel-industry database: real HTTP feed import
→ confirmed order, automatic room assignment, `x_booked` decrement,
cancellation frees the room; Channex webhook over HTTP → order with the
exact OTA amount.

## Setup (iCal / Airbnb example)

1. Channel Manager ▸ Channels ▸ New: type *iCal*, platform *Airbnb*.
2. Add a room mapping: pick the room-type product.
3. Copy the **Export URL** into Airbnb ▸ Calendar ▸ Import calendar.
4. Paste the Airbnb **calendar export link** into *Import URL*.
5. Click *Connect*. Done — sync runs every 10 minutes.
