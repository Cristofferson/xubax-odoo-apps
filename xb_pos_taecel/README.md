# POS Airtime & Bill Payments (TAECEL — Mexico)

Sell mobile airtime, data packages, bill payments and electronic PINs from the
Odoo Point of Sale through the TAECEL network. Built to install on **Odoo 18.0
and 19.0** from a single codebase.

## Status

This module is built in two layers, matching what TAECEL has documented to us.

### Confirmed and implemented — from the integrator manual we hold

The manual covers four endpoints (`POST`, `x-www-form-urlencoded`, auth via
`key` + `nip`):

| Endpoint | Used for |
|----------|----------|
| `getProducts` | Full catalog sync: **bolsas** (wallets), **carriers** (with their per-carrier input-field spec) and **products** (fixed amounts). |
| `getSales` | The reconciliation source we use today: every row carries a `TransID`, a final `Status` and the `Saldo Final` after the sale. Also our current wallet-balance source. |
| `RegistroCuenta` | Register an affiliate sub-account (reseller-network model). Wired in the transport layer. |
| `ReportarCompra` | Report a bank deposit to fund a wallet. |

Modelled on this:

* `xb.taecel.account` — credentials (manager-only, never sent to the POS),
  test/production mode, catalog sync, balance refresh.
* `xb.taecel.wallet` — one row per bolsa (Tiempo Aire, Pago de Servicios,
  Timbres CFDI). Tracked separately because TAECEL funds them from different
  bank accounts and balance is not transferable.
* `xb.taecel.carrier` — carrier type (catalog vs free-amount) and the `Campos`
  spec used to validate what the cashier types before charging.
* `xb.taecel.product` — the fixed-amount catalog, re-synced and archived (never
  deleted) so transactions keep their references.
* `xb.taecel.transaction` — records every sale attempt; settled from `getSales`.
* Crons: reconcile pending transactions (5 min) and refresh balances (30 min).

### Pending — the transactional API (a separate TAECEL document, not yet on file)

The manual we hold does **not** include the endpoint that actually dispatches a
recharge/payment, queries one transaction by `TransID`, or reads a balance
directly. TAECEL issues that after the *Levantamiento Tecnológico* and test
verification.

Everything pending is isolated and clearly marked:

* `TaecelClient.request_txn` / `status_txn` / `get_balance` — present so the
  shape is ready, marked `PENDING`, **not reachable from the POS**.
* `xb.taecel.transaction.action_dispatch` raises until the doc is verified.
* `const.py` marks every value `CONFIRMED` or `PENDING`.

When the transactional manual arrives, correcting `const.py` and wiring
`action_dispatch` is the whole job — no model or POS change.

### POS cashier UX — built (needs a live smoke test)

* A **"Recargas"** button in the product screen's expanded control bar (hidden
  when no TAECEL account is loaded).
* A **sale dialog** (`static/src/app/taecel_sale_dialog/`): pick carrier ->
  pick a fixed amount (catalog carriers) or type the amount (free-amount
  carriers) -> capture the reference, validated against the carrier's `Campos`
  spec (length, numeric/alphanumeric/email, confirm-twice) -> add a validated
  line to the current order. It contacts TAECEL never; it only builds a correct
  order line. A low-wallet warning shows when the charge exceeds the balance.
* The line rides on one generic service product (`XBTAECEL`), carrying the
  carrier, code, reference, wallet and fee as line metadata that rounds back to
  the server. On order payment, `pos.order._process_order` creates one
  `xb.taecel.transaction` per TAECEL line (state `draft`).

Static validation done: Python compiles, every XML is well-formed, all four JS
files pass ES-module syntax checks, and every view field resolves. **Not yet
run in a live POS** -- the OWL wiring (control-button xpath, `addLineToCurrentOrder`
custom-field round-trip, generic-product lookup) needs one smoke test on a test
database.

### Still pending

* The receipt block (folio, PIN, carrier note) -- waits on the dispatch result.
* Actual dispatch at payment time -- waits on the transactional API doc.

## Odoo 18 / 19 compatibility

All version divergence lives in `models/pos_compat.py` (Python) and will live in
`static/src/app/compat.js` (JS, once the POS screen exists). Verified against
both branches:

| | Odoo 18 | Odoo 19 |
|---|---|---|
| `_load_pos_data_domain` | `(self, data)` | `(self, data, config)` |
| `_load_pos_data_fields` | receives an **id** | receives a **recordset** |
| POS store path (JS) | `app/store/pos_store` | `app/services/pos_store` |
| `usePos` (JS) | `app/store/pos_hook` | `app/hooks/pos_hook` |

Python hooks are declared with `config=None` so both call arities bind; a helper
normalises id↔recordset.
