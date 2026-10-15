# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

MAX_BATCH = 200


class AnalitixKiosk(http.Controller):

    @http.route("/analitix_kiosk/stops", type="jsonrpc", auth="public")
    def kiosk_stops(self, access_token=None, stops=None, **kw):
        """The kiosk's stops (numbers only). Authenticated by the kiosk's own
        token: the page is public, so it never holds an Analitix device key."""
        config = request.env["pos.config"].sudo().search(
            [("access_token", "=", access_token or "x")], limit=1)
        if not config or not config._analitix_kiosk_data():
            return {"error": "not_enabled"}
        if not config.analitix_store_id.capture_enabled:
            # Paused by a person: the kiosk keeps them and sends them later.
            return {"paused": True}
        if not isinstance(stops, list):
            return {"error": "stops_must_be_a_list"}
        held = request.env["analitix.kiosk.session"].sudo().record_from_kiosk(
            config, stops[:MAX_BATCH])
        return {"ok": True, "held": held}
