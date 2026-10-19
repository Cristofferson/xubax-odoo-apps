# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields, http
from odoo.http import request

import hmac

from odoo.addons.xb_showroom_wall.controllers.wall import ShowroomWall, _screen, _tap_token, _tap_write

# The seller stays on the wall while the conversation goes on; it leaves after this much silence.
STAY_MINUTES = 3


class XbVaShowroomWall(ShowroomWall):

    def _wall_plugins(self, screen):
        return super()._wall_plugins(screen) + [{
            "css": "/xb_self_order_assistant_wall/static/src/wall/seller.css",
            "js": "/xb_self_order_assistant_wall/static/src/wall/seller.js",
        }]

    @http.route()
    def wall_tap(self, tap, **kw):
        """A phone tapped the counter's NFC stand while the seller is on the wall: the seller
        goes to that phone with the whole conversation. Otherwise, the wall's usual page."""
        screens = request.env["xb.showroom.screen"].sudo().search([("access_token", "!=", False)])
        screen = next((s for s in screens if hmac.compare_digest(_tap_token(s), tap or "")), None)
        if screen:
            _screen_found, conv = self._xb_va_wall_conv(screen.access_token)
            if conv:
                _tap_write(screen)  # the wall says «it's on your phone»
                return request.redirect(conv._xb_va_mobile_url(), local=False)
        return super().wall_tap(tap, **kw)

    def _xb_va_wall_conv(self, token):
        screen = _screen(token)
        if not screen:
            return screen, request.env["xb.va.conversation"]
        conv = request.env["xb.va.conversation"].sudo().search([
            ("wall_screen_id", "=", screen.id), ("presence", "=", "wall"),
            ("last_dt", ">=", fields.Datetime.now() - timedelta(minutes=STAY_MINUTES)),
        ], order="last_dt desc", limit=1)
        return screen, conv

    @http.route("/xb-va/w/<string:token>/state", type="jsonrpc", auth="public", methods=["POST"])
    def xb_va_wall_state(self, token):
        """What the wall shows of the seller: nothing, or its face, subtitles and voice."""
        screen, conv = self._xb_va_wall_conv(token)
        if not conv:
            return {"on": False}
        config = conv.config_id
        avatar = config.xb_va_avatar_id
        stamp = fields.Datetime.to_string(avatar.write_date) if avatar else ""
        return {
            "on": True,
            "name": config.xb_va_name or "Sofía",
            "face": avatar.image and "/xb-va/w/%s/avatar/image?unique=%s" % (token, stamp) or False,
            "full": avatar.image_full and "/xb-va/w/%s/avatar/image_full?unique=%s" % (token, stamp) or False,
            "idle": avatar.video_idle and "/xb-va/w/%s/avatar/video_idle?unique=%s" % (token, stamp) or False,
            "talk": avatar.video_talk and "/xb-va/w/%s/avatar/video_talk?unique=%s" % (token, stamp) or False,
            "text": conv.wall_text or "",
            "seq": conv.wall_seq,
            "audio": conv.wall_audio_id and "/xb-va/w/%s/voice/%s.mp3" % (token, conv.wall_audio_id.id) or False,
        }

    @http.route("/xb-va/w/<string:token>/avatar/<string:field>", type="http", auth="public", methods=["GET"])
    def xb_va_wall_avatar(self, token, field, **kw):
        screen, conv = self._xb_va_wall_conv(token)
        avatar = conv.config_id.xb_va_avatar_id.sudo() if conv else False
        if not avatar or field not in ("image", "image_full", "video_idle", "video_talk") or not avatar[field]:
            raise request.not_found()
        stream = request.env["ir.binary"]._get_stream_from(avatar, field)
        if field.startswith("video"):
            stream.mimetype = "video/mp4"
        return stream.get_response(max_age=86400)

    @http.route("/xb-va/w/<string:token>/voice/<int:att_id>.mp3", type="http", auth="public", methods=["GET"])
    def xb_va_wall_voice(self, token, att_id, **kw):
        screen, conv = self._xb_va_wall_conv(token)
        if not conv or conv.wall_audio_id.id != att_id:
            raise request.not_found()
        stream = request.env["ir.binary"]._get_stream_from(conv.wall_audio_id, "raw")
        stream.mimetype = "audio/mpeg"
        return stream.get_response()
