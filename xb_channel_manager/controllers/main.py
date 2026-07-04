# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ChannelManagerController(http.Controller):

    @http.route("/cm/ical/<string:token>.ics", type="http", auth="public",
                methods=["GET"], csrf=False)
    def ical_export(self, token, **kwargs):
        """Public per-listing iCal feed (secret token in the URL)."""
        listing = request.env["xb.cm.listing"].sudo().search([
            ("export_token", "=", token), ("active", "=", True)], limit=1)
        if not listing:
            return request.not_found()
        body = listing._ical_export_text()
        request.env["xb.cm.log"].sudo().log(
            listing.channel_id, "info", "ical_export",
            "%s: feed served (%s bytes)" % (listing.name, len(body)),
            listing=listing)
        return request.make_response(body, headers=[
            ("Content-Type", "text/calendar; charset=utf-8"),
            ("Content-Disposition",
             'attachment; filename="calendar-%s.ics"' % listing.id),
            ("Cache-Control", "no-cache"),
        ])

    @http.route("/cm/channex/webhook/<string:token>", type="http",
                auth="public", methods=["POST"], csrf=False)
    def channex_webhook(self, token, **kwargs):
        """Receive Channex push notifications (bookings, cancellations)."""
        channel = request.env["xb.cm.channel"].sudo().search([
            ("webhook_token", "=", token),
            ("channel_type", "=", "channex")], limit=1)
        if not channel:
            return request.not_found()
        try:
            payload = json.loads(
                request.httprequest.get_data(as_text=True) or "{}")
        except ValueError:
            return request.make_response(
                '{"error": "invalid json"}', status=400,
                headers=[("Content-Type", "application/json")])
        event = (payload.get("event") or "").lower()
        request.env["xb.cm.log"].sudo().log(
            channel, "info", "webhook",
            "event=%s payload=%s" % (event, str(payload)[:1000]))
        try:
            if "booking" in event or not event:
                client = None
                try:
                    client = channel._channex_client()
                except Exception:  # noqa: BLE001 — keys may be missing
                    pass
                request.env["xb.cm.reservation"].sudo() \
                    ._channex_stage_event(
                        channel, client,
                        payload.get("payload") or payload)
        except Exception as exc:  # noqa: BLE001
            _logger.exception("CM webhook processing failed")
            request.env["xb.cm.log"].sudo().log(
                channel, "error", "webhook", str(exc))
            return request.make_response(
                '{"status": "error"}', status=500,
                headers=[("Content-Type", "application/json")])
        return request.make_response(
            '{"status": "ok"}',
            headers=[("Content-Type", "application/json")])
