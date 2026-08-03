# -*- coding: utf-8 -*-
"""The ingest API — the only door into Analitix from outside Odoo.

Contract lives in ``doc/API.md``; this file is its implementation.

Six endpoints, all authenticated by a per-device API key and all scoped to
that device's own store:

===============================================  ==================================
``POST /analitix/api/v1/events``                 crossings, idempotent by uuid
``POST /analitix/api/v1/dwell``                  time in zones and at displays
``POST /analitix/api/v1/checkout``               the face at the till
``POST /analitix/api/v1/heartbeat``              "I am alive", plus agent health
``GET  /analitix/api/v1/config``                 the device's own configuration
``GET  /analitix/api/v1/staff_signatures``       staff vectors for local matching
===============================================  ==================================

Design rules this file follows, and why
---------------------------------------
* **Answer fast, work later.**  The response tells the agent whether it may drop
  the batch from its local buffer. Anything slower than a write — face matching,
  signage, CRM — is queued (``analitix.job``) and never blocks the reply.
* **Idempotent, not merely deduplicated.**  Already-seen uuids are reported in
  ``duplicates`` and counted as success, so a retrying agent gets a definitive
  "yes, I have it" and stops resending. A silent drop would loop forever.
* **Partial success is real success.**  One malformed row does not reject the
  batch; the good crossings are stored and the bad ones are itemised. A store's
  count must not hinge on a single bad timestamp.
* **Refuse plaintext.**  Biometric-adjacent payloads over HTTP are not
  acceptable (task 984, point 1), so non-TLS requests are rejected outright
  unless the deployment has explicitly opted out for a lab.
* **Never leak *why* a credential failed.**  Bad key, revoked key, archived
  device: one answer, ``invalid_credentials``. Distinguishing them tells an
  attacker which device UIDs exist.
"""
import json
import logging
from datetime import datetime, timezone

from odoo import fields, http, _
from odoo.http import request

from ..models.analitix_crypto import decode_embedding

_logger = logging.getLogger(__name__)

API_ROOT = "/analitix/api/v1"
MAX_BATCH = 1000
ALLOW_INSECURE_PARAM = "analitix.allow_insecure_ingest"


def _parse_ts(value):
    """ISO-8601 (with or without offset) to naive UTC, or ``None`` if unusable.

    Returning ``None`` rather than falling back to ``now()`` is deliberate: an
    event replayed from an agent's buffer hours after it happened must land on
    the hour it belongs to. Silently stamping it "now" would pile a whole
    outage's traffic onto the minute the link came back and make the day's
    curve a lie.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


class AnalitixAPI(http.Controller):

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------
    def _json(self, payload, status=200):
        return request.make_response(
            json.dumps(payload),
            headers=[("Content-Type", "application/json"),
                     ("Cache-Control", "no-store")],
            status=status,
        )

    def _bearer(self):
        auth = request.httprequest.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        # Some CCTV firmwares cannot set an Authorization header at all.
        return request.httprequest.headers.get("X-Analitix-Key")

    def _is_secure(self):
        """True when the request reached us over TLS.

        Behind nginx the Odoo socket is plain HTTP, so the proxy's
        ``X-Forwarded-Proto`` is the real signal — which is only trustworthy
        because ``proxy_mode`` is on and the proxy is the sole route in.
        """
        req = request.httprequest
        forwarded = req.headers.get("X-Forwarded-Proto", "")
        return req.scheme == "https" or forwarded.split(",")[0].strip() == "https"

    def _authenticate(self):
        """Return ``(device, error_response)``; exactly one is falsy."""
        if not self._is_secure():
            allow = request.env["ir.config_parameter"].sudo().get_param(
                ALLOW_INSECURE_PARAM, "0")
            if allow not in ("1", "True", "true"):
                return None, self._json({
                    "error": "tls_required",
                    "detail": "This endpoint accepts HTTPS only.",
                }, status=403)

        key = self._bearer()
        device = request.env["analitix.device"]._authenticate(key)
        if not device:
            # Logged, because a burst of these is either a misconfigured
            # rollout or somebody probing for a valid key.
            request.env["analitix.audit.log"].sudo().log(
                action="auth_failure", model="analitix.device",
                note=_("Rejected API key from %s",
                       request.httprequest.remote_addr or "?"))
            return None, self._json({"error": "invalid_credentials"}, status=401)

        if not device.store_id.capture_enabled:
            # Not an error the agent should retry past: it must back off and
            # keep buffering until a human resumes the store.
            return None, self._json({
                "error": "capture_paused",
                "detail": "Capture is paused for this store.",
                "retry_after_s": 300,
            }, status=423)
        return device, None

    def _body(self):
        try:
            return json.loads(request.httprequest.get_data() or b"{}"), None
        except (ValueError, TypeError):
            return None, self._json({"error": "bad_json"}, status=400)

    # ------------------------------------------------------------------
    # POST /events
    # ------------------------------------------------------------------
    @http.route("%s/events" % API_ROOT, type="http", auth="public",
                methods=["POST"], csrf=False, save_session=False)
    def ingest_events(self, **kw):
        device, error = self._authenticate()
        if error:
            return error
        body, error = self._body()
        if error:
            return error

        events = body.get("events")
        if not isinstance(events, list):
            return self._json({"error": "events_must_be_a_list"}, status=400)
        if len(events) > MAX_BATCH:
            return self._json({
                "error": "batch_too_large",
                "detail": "At most %d events per request." % MAX_BATCH,
            }, status=413)

        store = device.store_id
        door = device.door_id
        Event = request.env["analitix.event"].sudo()

        # One query resolves the whole batch's duplicates. Catching unique
        # violations row by row instead would abort the transaction and take
        # the batch's good events down with the repeat.
        incoming = [e.get("uuid") for e in events
                    if isinstance(e, dict) and e.get("uuid")]
        already = Event.existing_uuids(incoming)

        to_create, rejected, duplicates, payloads = [], [], [], []
        seen_in_batch = set()
        for index, raw in enumerate(events):
            if not isinstance(raw, dict):
                rejected.append({"index": index, "reason": "not_an_object"})
                continue
            uuid = raw.get("uuid")
            if not uuid:
                rejected.append({"index": index, "reason": "missing_uuid"})
                continue
            if uuid in already or uuid in seen_in_batch:
                duplicates.append(uuid)
                continue
            direction = raw.get("direction", "in")
            if direction not in ("in", "out"):
                rejected.append({"index": index, "reason": "bad_direction"})
                continue
            event_time = _parse_ts(raw.get("ts"))
            if not event_time:
                rejected.append({"index": index, "reason": "bad_timestamp"})
                continue
            try:
                count = int(raw.get("count") or 1)
            except (TypeError, ValueError):
                rejected.append({"index": index, "reason": "bad_count"})
                continue
            if count < 1:
                rejected.append({"index": index, "reason": "bad_count"})
                continue

            vals = {
                "uuid": uuid,
                "device_id": device.id,
                "store_id": store.id,
                "door_id": door.id if door else False,
                "direction": direction,
                "count": count,
                "event_time": event_time,
                "track_ref": raw.get("track") or False,
                "counted": True,
                "liveness_score": self._float(raw.get("liveness")),
                "embedding_model": raw.get("embedding_model") or False,
            }
            self._apply_staff_rules(vals, raw, device, store, door)
            to_create.append(vals)
            payloads.append(raw)
            seen_in_batch.add(uuid)

        created = Event.create(to_create) if to_create else Event.browse()

        # Demographics are attached synchronously: it is a plain insert with no
        # matching involved, and deferring it would leave the reading orphaned
        # from the crossing that produced it if the job queue fell behind.
        self._record_demographics(created, payloads, store)

        # Anything needing a face comparison goes to the queue, so the edge is
        # never held waiting while a vector is matched against everyone seen in
        # the last few hours.
        pending = created.filtered("pending_embedding")
        if pending:
            staff_pending = pending.filtered(lambda e: e.counted)
            if staff_pending and store.reid_enabled:
                request.env["analitix.job"].sudo().enqueue(
                    "visitor_resolve", {"event_ids": staff_pending.ids},
                    store=store, priority=5)
            elif staff_pending:
                request.env["analitix.job"].sudo().enqueue(
                    "staff_match", {"event_ids": staff_pending.ids},
                    store=store, priority=5)

        device._mark_seen(
            agent_version=body.get("agent_version"),
            queue_size=body.get("queue_size"))
        if created:
            device.sudo().last_event_at = max(created.mapped("event_time"))

        return self._json({
            "ok": True,
            "stored": len(created),
            "duplicates": len(duplicates),
            "rejected": rejected,
            # The agent clears everything acknowledged here. Duplicates count
            # as acknowledged — we already have them.
            "acknowledged": [v["uuid"] for v in to_create] + duplicates,
        })

    @staticmethod
    def _float(value):
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _record_demographics(self, events, payloads, store):
        """Attach an age/gender/emotion reading to each crossing that carried one."""
        if not store.demographics_enabled or not events:
            return
        Demographic = request.env["analitix.demographic"].sudo()
        for event, raw in zip(events, payloads):
            reading = Demographic.record(
                store, event.door_id, raw.get("demographics"),
                liveness=event.liveness_score, when=event.event_time)
            if reading and event.visitor_id:
                # Only when the visit is already known; otherwise the resolution
                # job links it, which is the usual path.
                event.visitor_id.sudo().demographic_id = reading.id
            elif reading:
                event.sudo().pending_demographic_id = reading.id

    def _apply_staff_rules(self, vals, raw, device, store, door):
        """Decide whether this crossing counts as a visitor.

        Three paths, in order of preference:
        1. the door is flagged as not counting visitors (service/emergency);
        2. the edge already identified an employee — trusted, since it holds
           the same signatures Odoo gave it and never sent a face over the wire;
        3. an embedding came with the event — matched here if it is cheap, or
           deferred to a job so the agent is not kept waiting.
        """
        if door and not door.counts_visitors:
            vals["counted"] = False
            return
        if not store.exclude_staff:
            return

        if raw.get("is_staff"):
            vals["counted"] = False
            vals["match_score"] = float(raw.get("staff_score") or 0.0)
            employee_ref = raw.get("employee_ref")
            if employee_ref:
                signature = request.env["analitix.staff.signature"].sudo().search([
                    ("store_id", "=", store.id),
                    ("employee_id.barcode", "=", employee_ref),
                ], limit=1)
                if signature:
                    vals["staff_id"] = signature.employee_id.id
                    signature._register_match()
            return

        vector = decode_embedding(raw.get("embedding"))
        if not vector:
            return
        crypto = request.env["analitix.crypto"].sudo()
        Signature = request.env["analitix.staff.signature"].sudo()
        sig_id, employee_id, score = Signature.match(
            store, vector, raw.get("embedding_model") or "buffalo_l")
        if employee_id:
            vals.update({
                "counted": False, "staff_id": employee_id, "match_score": score,
            })
            Signature.browse(sig_id)._register_match()
        else:
            # No match now, but phase 2 and 3 will want this vector for
            # re-identification. Park it encrypted for the async pass.
            vals["pending_embedding"] = crypto.encrypt_vector(
                crypto.normalize(vector))
            vals["match_score"] = score

    # ------------------------------------------------------------------
    # POST /dwell — time spent in zones and at displays
    # ------------------------------------------------------------------
    @http.route("%s/dwell" % API_ROOT, type="http", auth="public",
                methods=["POST"], csrf=False, save_session=False)
    def ingest_dwell(self, **kw):
        """Report how long tracked people have spent in zones and at displays.

        Sent as a *running total* while the person is still standing there, not
        once at the end: a lost-sale nudge is worthless if it arrives after the
        customer has walked out. Odoo upserts on
        ``(visit, zone, entered_at)``, so repeating the same observation with a
        bigger number updates one row rather than creating a dozen.

        The agent identifies people by the ``track`` it assigned them at the
        door. Odoo resolves that to a visit; an unknown track is skipped
        quietly, because a person who walked in before the agent restarted has
        no visit to attach to and that is not an error.
        """
        device, error = self._authenticate()
        if error:
            return error
        body, error = self._body()
        if error:
            return error

        store = device.store_id
        observations = body.get("dwells")
        if not isinstance(observations, list):
            return self._json({"error": "dwells_must_be_a_list"}, status=400)
        if len(observations) > MAX_BATCH:
            return self._json({"error": "batch_too_large"}, status=413)

        Zone = request.env["analitix.zone"].sudo()
        Poi = request.env["analitix.poi"].sudo()
        Dwell = request.env["analitix.zone.dwell"].sudo()
        Attention = request.env["analitix.poi.attention"].sudo()
        LostSale = request.env["analitix.lost.sale"].sudo()

        stored, skipped = 0, 0
        for raw in observations:
            if not isinstance(raw, dict):
                skipped += 1
                continue
            visitor = self._resolve_visit(store, raw)
            if not visitor:
                skipped += 1
                continue
            started = _parse_ts(raw.get("since"))
            try:
                seconds = int(raw.get("seconds") or 0)
            except (TypeError, ValueError):
                skipped += 1
                continue
            if not started or seconds < 0:
                skipped += 1
                continue

            if raw.get("poi"):
                poi = Poi.search([
                    ("store_id", "=", store.id),
                    ("code", "=", raw["poi"]),
                ], limit=1)
                if poi:
                    Attention.record(visitor, poi, started, seconds)
                    stored += 1
                    continue
                skipped += 1
                continue

            zone = Zone.search([
                ("store_id", "=", store.id),
                ("code", "=", raw.get("zone") or ""),
            ], limit=1) or device.zone_id
            if not zone:
                skipped += 1
                continue

            def _confidence(value):
                try:
                    return float(value or 0.0)
                except (TypeError, ValueError):
                    return 0.0

            dwell = Dwell.record(
                visitor, zone, started, seconds,
                served=bool(raw.get("served")),
                # Optional, and ignored entirely unless the store asked for the
                # sustained-expression nudge. An agent that reports it to a
                # store that did not switch it on changes nothing.
                emotion=raw.get("emotion") or None,
                emotion_confidence=_confidence(raw.get("emotion_confidence")))
            stored += 1
            # Evaluated inline rather than queued: this is the one thing in the
            # whole pipeline that is worthless late. Everything it can trigger
            # (the alert itself, WhatsApp) is already non-blocking.
            LostSale._evaluate_dwell(dwell)

        device._mark_seen(
            agent_version=body.get("agent_version"),
            queue_size=body.get("queue_size"))
        return self._json({"ok": True, "stored": stored, "skipped": skipped})

    def _resolve_visit(self, store, raw):
        """Find the visit an observation belongs to, by edge track id."""
        track = raw.get("track")
        if not track:
            return request.env["analitix.visitor"]
        event = request.env["analitix.event"].sudo().search([
            ("store_id", "=", store.id),
            ("track_ref", "=", str(track)),
            ("visitor_id", "!=", False),
        ], order="event_time desc", limit=1)
        return event.visitor_id

    # ------------------------------------------------------------------
    # POST /checkout — the face at the till
    # ------------------------------------------------------------------
    @http.route("%s/checkout" % API_ROOT, type="http", auth="public",
                methods=["POST"], csrf=False, save_session=False)
    def ingest_checkout(self, **kw):
        """Attribute a ticket to the visit that produced it.

        The till camera posts the payer's embedding with the POS reference. The
        heavy part — comparing it against everyone who came in — is queued, so
        nothing here can ever make a cashier wait while a customer stands at the
        counter.
        """
        device, error = self._authenticate()
        if error:
            return error
        body, error = self._body()
        if error:
            return error

        store = device.store_id
        reference = body.get("pos_reference") or body.get("order_ref")
        if not reference:
            return self._json({"error": "missing_pos_reference"}, status=400)

        order = request.env["pos.order"].sudo().search([
            ("pos_reference", "=", reference)], limit=1)
        if not order:
            # The ticket may not have synced yet. Not an error the agent should
            # retry against: the group-level fallback already attributes it.
            return self._json({"ok": True, "queued": False,
                               "detail": "order_not_found_yet"})

        request.env["analitix.job"].sudo().enqueue(
            "match_checkout", {
                "order_id": order.id,
                "store_id": store.id,
                "embedding": body.get("embedding"),
            }, store=store, priority=3)
        device._mark_seen()
        return self._json({"ok": True, "queued": True})

    # ------------------------------------------------------------------
    # POST /heartbeat
    # ------------------------------------------------------------------
    @http.route("%s/heartbeat" % API_ROOT, type="http", auth="public",
                methods=["POST"], csrf=False, save_session=False)
    def heartbeat(self, **kw):
        device, error = self._authenticate()
        if error:
            return error
        body, error = self._body()
        if error:
            return error
        device._mark_seen(
            agent_version=body.get("agent_version"),
            queue_size=body.get("queue_size"))
        store = device.store_id
        return self._json({
            "ok": True,
            "server_time": fields.Datetime.now().isoformat() + "Z",
            # Handing the interval back on every beat means retuning a whole
            # fleet is a field change in Odoo, not a visit to each store.
            "heartbeat_interval_s": store.heartbeat_interval_s,
            "capture_enabled": store.capture_enabled,
        })

    # ------------------------------------------------------------------
    # GET /config
    # ------------------------------------------------------------------
    @http.route("%s/config" % API_ROOT, type="http", auth="public",
                methods=["GET"], csrf=False, save_session=False)
    def config(self, **kw):
        device, error = self._authenticate()
        if error:
            return error
        store = device.store_id
        try:
            device_config = json.loads(device.config_json or "{}")
        except ValueError:
            device_config = {}
        return self._json({
            "ok": True,
            "device": {
                "uid": device.device_uid,
                "name": device.name,
                "role": device.role,
                "hardware": device.kind,
                "config": device_config,
            },
            "door": {
                "id": device.door_id.id,
                "name": device.door_id.name,
                "counts_visitors": device.door_id.counts_visitors,
            } if device.door_id else None,
            "store": {
                "id": store.id,
                "name": store.name,
                "tz": store.tz,
                "capture_enabled": store.capture_enabled,
                "exclude_staff": store.exclude_staff,
                "staff_match_threshold": store.staff_match_threshold,
                "heartbeat_interval_s": store.heartbeat_interval_s,
            },
        })

    # ------------------------------------------------------------------
    # GET /staff_signatures
    # ------------------------------------------------------------------
    @http.route("%s/staff_signatures" % API_ROOT, type="http", auth="public",
                methods=["GET"], csrf=False, save_session=False)
    def staff_signatures(self, **kw):
        """Hand the agent its own store's staff vectors for local matching.

        This is the privacy-preferable path: matching on the edge means no
        embedding ever travels, and the crossing arrives already labelled. The
        vectors are returned decrypted because the agent has to compare them —
        which is exactly why this endpoint is scoped to one store, why the link
        is TLS-only, and why the agent's own disk buffer is encrypted too.
        """
        device, error = self._authenticate()
        if error:
            return error
        store = device.store_id
        crypto = request.env["analitix.crypto"].sudo()
        payload = []
        for sig in request.env["analitix.staff.signature"].sudo().search([
                ("store_id", "=", store.id), ("active", "=", True)]):
            vector = crypto.decrypt_vector(sig.embedding)
            if not vector:
                continue
            payload.append({
                "id": sig.id,
                "employee_ref": sig.employee_id.barcode or str(sig.employee_id.id),
                "model": sig.model_name,
                "vector": crypto.normalize(vector),
            })
        request.env["analitix.audit.log"].sudo().log(
            action="read_sensitive", model="analitix.staff.signature",
            store=store, count=len(payload),
            note=_("Edge device %s pulled staff signatures", device.device_uid))
        return self._json({
            "ok": True,
            "threshold": store.staff_match_threshold,
            "enabled": store.exclude_staff,
            "signatures": payload,
        })
