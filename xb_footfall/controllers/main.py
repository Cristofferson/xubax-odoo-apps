# -*- coding: utf-8 -*-
import json
import logging

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class FootfallController(http.Controller):
    """Sensor-agnostic ingest endpoint.

    Any source (Hikvision/Dahua ISAPI relay, DIY edge, IR beam) authenticates
    with a per-device Bearer token and POSTs a batch of crossing events. No
    image is ever transmitted — only the count.

        POST /xb_footfall/ingest
        Authorization: Bearer <device_token>
        {
          "device_uid": "anello-morelia-puerta1",
          "events": [
            {"ts": "2026-06-28T14:32:05-06:00", "direction": "in",  "count": 1},
            {"ts": "2026-06-28T14:32:09-06:00", "direction": "out", "count": 1}
          ]
        }
    """

    def _json(self, payload, status=200):
        return request.make_response(
            json.dumps(payload),
            headers=[("Content-Type", "application/json")],
            status=status,
        )

    def _bearer(self):
        auth = request.httprequest.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        return None

    @http.route("/xb_footfall/ingest", type="http", auth="public",
                methods=["POST"], csrf=False, save_session=False)
    def ingest(self, **kw):
        token = self._bearer()
        if not token:
            return self._json({"error": "missing_bearer_token"}, status=401)

        device = request.env["xb.footfall.device"].sudo().search(
            [("access_token", "=", token), ("active", "=", True)], limit=1)
        if not device:
            return self._json({"error": "invalid_token"}, status=403)

        try:
            body = json.loads(request.httprequest.get_data() or b"{}")
        except (ValueError, TypeError):
            return self._json({"error": "bad_json"}, status=400)

        events = body.get("events") or []
        if not isinstance(events, list):
            return self._json({"error": "events_must_be_list"}, status=400)

        Event = request.env["xb.footfall.event"].sudo()
        created = 0
        for ev in events:
            if not isinstance(ev, dict):
                continue
            direction = ev.get("direction", "in")
            if direction not in ("in", "out"):
                continue
            vals = {
                "device_id": device.id,
                "direction": direction,
                "count": int(ev.get("count") or 1),
                "event_time": ev.get("ts") or fields.Datetime.now(),
            }
            if ev.get("seq") is not None:
                vals["seq"] = int(ev["seq"])
            Event.create(vals)
            created += 1

        device.sudo().last_seen = fields.Datetime.now()
        return self._json({"ok": True, "stored": created})
