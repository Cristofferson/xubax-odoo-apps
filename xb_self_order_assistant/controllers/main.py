# -*- coding: utf-8 -*-
import hmac
import json
import logging
from datetime import timedelta

from markupsafe import Markup

from werkzeug.exceptions import Forbidden

from odoo import _, fields, http
from odoo.http import request

from odoo.addons.pos_self_order.controllers.self_entry import PosSelfKiosk

_logger = logging.getLogger(__name__)

XB_MAX_TEXT = 600
XB_MAX_AUDIO = 4 * 1024 * 1024


class XbVirtualSeller(PosSelfKiosk):

    def _xb_va_config(self, config_id, access_token, m=None):
        """The kiosk (its access token), or a conversation that moved to the customer's phone
        (its own mobile token: that conversation only, for a limited time)."""
        request.xb_va_mobile = None
        if m:
            conv = request.env["xb.va.conversation"].sudo()._xb_va_mobile(m)
            if not conv or conv.config_id.id != int(config_id):
                raise Forbidden()
            request.xb_va_mobile = conv
            pos_config = conv.config_id
        elif not access_token:
            raise Forbidden()
        else:
            pos_config, _table, _token = self._verify_entry_access(str(config_id), access_token)
        pos_config = pos_config.sudo()
        if not pos_config.xb_va_enabled:
            raise request.not_found()
        # Messages in the kiosk's language (these routes are not website routes).
        lang = request.cookies.get("frontend_lang") or pos_config.company_id.partner_id.lang
        if lang and lang in dict(request.env["res.lang"].get_installed()):
            request.update_context(lang=lang)
            pos_config = pos_config.with_context(lang=lang)
        return pos_config

    def _xb_va_conversation(self, config, token, create=True):
        mobile = getattr(request, "xb_va_mobile", None)
        if mobile:
            return mobile
        Conv = request.env["xb.va.conversation"].sudo()
        conv = Conv.search([("config_id", "=", config.id), ("token", "=", token or "")], limit=1) if token else Conv
        if not conv and create:
            conv = Conv.create({"config_id": config.id})
        return conv

    @http.route("/xb-va/<int:config_id>/chat", type="jsonrpc", auth="public", methods=["POST"])
    def xb_va_chat(self, config_id, access_token=None, m=None, token=None, text=None):
        """The customer said or typed something: the seller answers and tells the screen what to show."""
        config = self._xb_va_config(config_id, access_token, m)
        text = (text or "").strip()[:XB_MAX_TEXT]
        if not text:
            return {"token": token, "reply": ""}
        if config._xb_va_over_budget():
            return {"token": token, "reply": _("I can't attend right now; please ask at the counter."),
                    "unavailable": True, "products": []}
        conv = self._xb_va_conversation(config, token)
        try:
            result = conv._xb_va_answer(text)
        except Exception:
            _logger.exception("xb_va chat failed (kiosk %s)", config.id)
            return {"token": conv.token, "reply": _("Sorry, I had a problem. Can you repeat it?"),
                    "products": [], "error": True}
        products = []
        for tmpl in request.env["product.template"].sudo().browse(result["products"]).exists():
            products.append({"id": tmpl.id, "name": tmpl.name,
                             "price": conv._xb_va_price_label(tmpl)})
        return {
            "token": conv.token,
            "reply": result["reply"],
            "products": products,
            "open": result.get("open") or False,
            "handoff": result.get("handoff") or False,
            "ask_phone": result.get("ask_phone") or False,
            "actions": result.get("actions") or [],
        }

    @http.route("/xb-va/<int:config_id>/listen", type="http", auth="public", methods=["POST"], csrf=False)
    def xb_va_listen(self, config_id, access_token=None, m=None, token=None, seconds=0, audio=None, **kw):
        """Speech to text: the kiosk sends what the microphone recorded."""
        config = self._xb_va_config(config_id, access_token, m)
        if not audio:
            return request.make_json_response({"text": ""})
        data = audio.read(XB_MAX_AUDIO + 1)
        if len(data) > XB_MAX_AUDIO:
            return request.make_json_response({"text": "", "error": "too_long"})
        conv = self._xb_va_conversation(config, token)
        try:
            text = conv._xb_va_listen(data, audio.filename, audio.mimetype, float(seconds or 0))
        except Exception:
            _logger.exception("xb_va listen failed (kiosk %s)", config.id)
            return request.make_json_response({"token": conv.token, "text": "", "error": "listen"})
        return request.make_json_response({"token": conv.token, "text": text})

    @http.route("/xb-va/<int:config_id>/speak", type="http", auth="public", methods=["POST"], csrf=False)
    def xb_va_speak(self, config_id, access_token=None, m=None, token=None, text=None, **kw):
        """Text to speech in the voice chosen for this kiosk (MP3)."""
        config = self._xb_va_config(config_id, access_token, m)
        text = (text or "").strip()[:XB_MAX_TEXT * 2]
        if not text or not config.xb_va_speak:
            return request.make_response(b"", headers=[("Content-Type", "audio/mpeg")])
        try:
            audio, new = request.env["xb.va.conversation"].sudo()._xb_va_speech(config, text)
        except Exception:
            _logger.exception("xb_va speak failed (kiosk %s)", config.id)
            return request.make_response(b"", status=502)
        if new and token:
            conv = self._xb_va_conversation(config, token, create=False)
            if conv:
                conv.voice_chars += len(text)
                conv._xb_va_recompute_cost()
        return request.make_response(audio, headers=[("Content-Type", "audio/mpeg"),
                                                     ("Cache-Control", "private, max-age=86400")])

    @http.route("/xb-va/<int:config_id>/handoff", type="jsonrpc", auth="public", methods=["POST"])
    def xb_va_handoff(self, config_id, access_token=None, m=None, token=None):
        """The customer pressed «call a person»."""
        config = self._xb_va_config(config_id, access_token, m)
        conv = self._xb_va_conversation(config, token)
        last = (conv.transcript or "").strip().splitlines()[-4:]
        summary = _("The customer pressed the button to call a person.")
        if last:
            summary += "\n" + "\n".join(last)
        done = config._xb_va_handoff(conv, summary)
        conv.handoff = True
        return {"token": conv.token, "done": bool(done)}

    @http.route("/xb-va/<int:config_id>/sample", type="http", auth="user", methods=["GET"])
    def xb_va_sample(self, config_id, **kw):
        """The greeting in the kiosk's voice, for the owner choosing a voice in the settings."""
        if not request.env.user.has_group("point_of_sale.group_pos_manager"):
            raise Forbidden()
        config = request.env["pos.config"].browse(config_id).exists()
        if not config:
            raise request.not_found()
        text = config.xb_va_greeting or config._xb_va_default("greeting")
        audio, _new = request.env["xb.va.conversation"].sudo()._xb_va_speech(config.sudo(), text)
        return request.make_response(audio, headers=[("Content-Type", "audio/mpeg")])

    @http.route("/xb-va/<int:config_id>/avatar/<string:kind>", type="http", auth="public", methods=["GET"])
    def xb_va_avatar(self, config_id, kind, access_token=None, m=None, **kw):
        """The seller's face, full screen picture or videos, for the kiosk."""
        config = self._xb_va_config(config_id, access_token, m)
        field = {"face": "image", "full": "image_full", "idle": "video_idle", "talk": "video_talk"}.get(kind)
        avatar = config.xb_va_avatar_id.sudo()
        if not field or not avatar or not avatar[field]:
            raise request.not_found()
        stream = request.env["ir.binary"]._get_stream_from(avatar, field)
        if kind in ("idle", "talk"):
            stream.mimetype = "video/mp4"
        return stream.get_response(max_age=86400)

    @http.route("/xb-va/<int:config_id>/share", type="jsonrpc", auth="public", methods=["POST"])
    def xb_va_share(self, config_id, access_token=None, m=None, token=None, channel=None, phone=None):
        """Send the customer, to the phone they typed, what they saw and the conversation."""
        config = self._xb_va_config(config_id, access_token, m)
        conv = self._xb_va_conversation(config, token, create=False)
        digits = "".join(c for c in (phone or "") if c.isdigit())
        if not conv or len(digits) < 8 or channel not in conv._xb_va_share_channels(config):
            return {"ok": False, "error": _("Check the number and try again.")}
        try:
            with request.env.cr.savepoint():
                conv._xb_va_share(channel, phone)
        except Exception:
            _logger.exception("xb_va share failed (kiosk %s)", config.id)
            return {"ok": False, "error": _("It could not be sent. Please ask at the counter.")}
        return {"ok": True}

    @http.route("/xb-va/s/<string:share_token>", type="http", auth="public", methods=["GET"], sitemap=False)
    def xb_va_selection(self, share_token, **kw):
        """Public page the customer receives: the products they saw and the conversation."""
        conv = request.env["xb.va.conversation"].sudo().search([("share_token", "=", share_token)], limit=1)
        if not share_token or len(share_token) < 20 or not conv:
            raise request.not_found()
        lang = conv.partner_id.lang or conv.config_id.company_id.partner_id.lang
        conv = conv.with_context(lang=lang)
        products = [{"tmpl": t, "price": conv._xb_va_price_label(t),
                     "url": t.website_url if t._fields.get("website_url") and t._fields.get("is_published") and t.is_published else False}
                    for t in conv.product_ids]
        return request.render("xb_self_order_assistant.selection_page", {
            "conv": conv, "company": conv.config_id.company_id, "products": products,
            "lines": conv._xb_va_transcript_lines(), "seller": conv.config_id.xb_va_name or "Sofía",
            "labels": {
                "intro": conv.env._("What you saw with %s at our kiosk.", conv.config_id.xb_va_name or "Sofía"),
                "selection": conv.env._("Your selection"),
                "conversation": conv.env._("Our conversation"),
            },
        })

    @http.route("/xb-va/s/<string:share_token>/img/<int:product_id>", type="http", auth="public", methods=["GET"])
    def xb_va_selection_image(self, share_token, product_id, **kw):
        conv = request.env["xb.va.conversation"].sudo().search([("share_token", "=", share_token)], limit=1)
        tmpl = conv.product_ids.filtered(lambda t: t.id == product_id) if conv and len(share_token) >= 20 else False
        if not tmpl:
            raise request.not_found()
        return request.env["ir.binary"]._get_image_stream_from(tmpl, "image_512").get_response(max_age=86400)

    # ------------------------------------------------------------------ live voice
    @http.route("/xb-va/<int:config_id>/live", type="jsonrpc", auth="public", methods=["POST"])
    def xb_va_live(self, config_id, access_token=None, m=None, token=None):
        """Opens a live voice conversation: a short-lived key for the kiosk browser."""
        config = self._xb_va_config(config_id, access_token, m)
        if config.xb_va_engine != "realtime" or config._xb_va_over_budget():
            return {"ok": False}
        conv = self._xb_va_conversation(config, token)
        try:
            session = conv._xb_va_live_session()
        except Exception:
            _logger.exception("xb_va live session failed (kiosk %s)", config.id)
            return {"ok": False, "token": conv.token}
        return dict(session, ok=True, token=conv.token)

    @http.route("/xb-va/<int:config_id>/tool", type="jsonrpc", auth="public", methods=["POST"])
    def xb_va_tool(self, config_id, access_token=None, m=None, token=None, name=None, args=None):
        """The live model asks Odoo to do something (search, show products, call a person...)."""
        config = self._xb_va_config(config_id, access_token, m)
        conv = self._xb_va_conversation(config, token, create=False)
        if not conv or name not in {t["name"] for t in conv._xb_va_tools()}:
            return {"output": "Herramienta no disponible.", "ui": {}}
        ui = conv._xb_va_new_ui()
        output, _error = conv._xb_va_run_tool(name, args if isinstance(args, dict) else {}, ui)
        return {"output": output, "ui": ui}

    @http.route("/xb-va/<int:config_id>/live_log", type="jsonrpc", auth="public", methods=["POST"])
    def xb_va_live_log(self, config_id, access_token=None, m=None, token=None, who=None, text=None, usage=None):
        """What was said (for the history) and what the live model used (for the cost)."""
        config = self._xb_va_config(config_id, access_token, m)
        conv = self._xb_va_conversation(config, token, create=False)
        if not conv:
            return {"ok": False}
        if text and who in ("customer", "seller"):
            conv._xb_va_live_log(who, str(text)[:XB_MAX_TEXT * 2])
        if isinstance(usage, dict):
            conv._xb_va_live_usage(usage)
        return {"ok": True, "available": not config._xb_va_over_budget()}

    @http.route("/xb-va/<int:config_id>/scan", type="jsonrpc", auth="public", methods=["POST"])
    def xb_va_scan(self, config_id, access_token=None, m=None, token=None, code=None):
        """The kiosk reader read a card or a barcode."""
        config = self._xb_va_config(config_id, access_token, m)
        if not config.xb_va_scan or not code:
            return {"ok": False}
        conv = self._xb_va_conversation(config, token)
        result = conv._xb_va_scan(str(code)[:300])
        return dict(result, ok=True, token=conv.token)

    # ------------------------------------------------------------------ moving to the phone
    @http.route("/xb-va/<int:config_id>/qr.png", type="http", auth="public", methods=["GET"])
    def xb_va_qr(self, config_id, access_token=None, m=None, token=None, **kw):
        """QR of the link that takes THIS conversation to the customer's phone."""
        config = self._xb_va_config(config_id, access_token, m)
        conv = self._xb_va_conversation(config, token, create=False)
        if not conv:
            raise request.not_found()
        png = request.env["ir.actions.report"].barcode("QR", conv._xb_va_mobile_url(), width=480, height=480)
        return request.make_response(png, headers=[("Content-Type", "image/png"), ("Cache-Control", "no-store")])

    @http.route("/xb-va/<int:config_id>/start", type="jsonrpc", auth="public", methods=["POST"])
    def xb_va_start(self, config_id, access_token=None, m=None, token=None):
        """A conversation for the kiosk, before anything was said (e.g. to take it to the phone)."""
        config = self._xb_va_config(config_id, access_token, m)
        return {"token": self._xb_va_conversation(config, token).token}

    @http.route("/xb-va/<int:config_id>/end", type="jsonrpc", auth="public", methods=["POST"])
    def xb_va_end(self, config_id, access_token=None, m=None, token=None):
        """The kiosk let the customer go: the seller leaves the wall too."""
        config = self._xb_va_config(config_id, access_token, m)
        conv = self._xb_va_conversation(config, token, create=False)
        if conv and conv.presence == "wall":
            conv.presence = "kiosk"
        return {"ok": True}

    @http.route("/xb-va/<int:config_id>/presence", type="jsonrpc", auth="public", methods=["POST"])
    def xb_va_presence(self, config_id, access_token=None, m=None, token=None):
        """Where the seller is now (the kiosk lets go when the customer took it to their phone)."""
        config = self._xb_va_config(config_id, access_token, m)
        conv = self._xb_va_conversation(config, token, create=False)
        return {"presence": conv.presence if conv else False}

    @http.route("/xb-va/<int:config_id>/history", type="jsonrpc", auth="public", methods=["POST"])
    def xb_va_history(self, config_id, access_token=None, m=None, token=None):
        """The conversation so far and the products shown, for the phone that continues it."""
        config = self._xb_va_config(config_id, access_token, m)
        conv = self._xb_va_conversation(config, token, create=False)
        if not conv:
            return {"messages": [], "products": []}
        params = "m=%s" % m if m else "access_token=%s" % access_token
        return {"messages": [{"who": who, "text": text} for who, text in conv._xb_va_transcript_lines()],
                "products": conv._xb_va_cards(conv.product_ids[-6:], params), "token": conv.token}

    @http.route("/xb-va/<int:config_id>/cards", type="jsonrpc", auth="public", methods=["POST"])
    def xb_va_cards(self, config_id, access_token=None, m=None, token=None, ids=None):
        config = self._xb_va_config(config_id, access_token, m)
        conv = self._xb_va_conversation(config, token, create=False)
        tmpls = request.env["product.template"]
        for pid in (ids or [])[:6]:
            tmpls |= conv._xb_va_product(pid) if conv else tmpls
        params = "m=%s" % m if m else "access_token=%s" % access_token
        return {"cards": conv._xb_va_cards(tmpls, params) if conv else []}

    @http.route("/xb-va/<int:config_id>/img/<int:product_id>", type="http", auth="public", methods=["GET"])
    def xb_va_img(self, config_id, product_id, access_token=None, m=None, **kw):
        config = self._xb_va_config(config_id, access_token, m)
        tmpl = request.env["xb.va.conversation"].sudo().new({"config_id": config.id})._xb_va_product(product_id)
        if not tmpl:
            raise request.not_found()
        return request.env["ir.binary"]._get_image_stream_from(tmpl, "image_512").get_response(max_age=86400)

    @http.route("/xb-va/k/<int:config_id>/<string:tap>", type="http", auth="public", methods=["GET"], sitemap=False)
    def xb_va_kiosk_tap(self, config_id, tap, **kw):
        """A phone touched the kiosk's NFC sticker: the seller goes to it with the conversation going
        on right now (or a new one starts there)."""
        config = request.env["pos.config"].sudo().browse(config_id).exists()
        if not config or not config.xb_va_enabled or not hmac.compare_digest(config._xb_va_tap_token(), tap or ""):
            raise request.not_found()
        Conv = request.env["xb.va.conversation"].sudo()
        conv = Conv.search([("config_id", "=", config.id), ("presence", "in", ("kiosk", "wall")),
                            ("last_dt", ">=", fields.Datetime.now() - timedelta(minutes=5))],
                           order="last_dt desc", limit=1) or Conv.create({"config_id": config.id})
        return request.redirect(conv._xb_va_mobile_url(), local=False)

    @http.route("/xb-va/m/<string:mobile_token>", type="http", auth="public", methods=["GET"], sitemap=False)
    def xb_va_mobile(self, mobile_token, **kw):
        """The seller on the customer's phone: the same conversation continues here."""
        conv = request.env["xb.va.conversation"].sudo()._xb_va_mobile(mobile_token)
        if not conv or not conv.config_id.xb_va_enabled:
            raise request.not_found()
        if conv.presence != "phone":
            conv.write({"presence": "phone", "went_phone": True})
        config = conv.config_id
        lang = config.company_id.partner_id.lang or "es_MX"
        config = config.with_context(lang=lang)
        settings = config._xb_va_settings()
        return request.render("xb_self_order_assistant.mobile_page", {
            "config": config, "company": config.company_id, "lang": lang,
            "boot": Markup(json.dumps({
                "config_id": config.id, "m": mobile_token, "token": conv.token,
                "name": settings["name"], "engine": settings["engine"], "speak": settings["speak"],
                "rt_voice": settings["rt_voice"],
                "avatar": settings["avatar"], "share": settings["share"],
                "texts": {
                    "placeholder": config.env._("Write your question…"),
                    "listening": config.env._("Listening…"), "thinking": config.env._("Thinking…"),
                    "speaking": config.env._("Speaking…"), "talk": config.env._("Tap to talk"),
                    "welcome": config.env._("Here I am, on your phone. We can keep talking."),
                    "error": config.env._("Sorry, I can't talk right now. You can write your question."),
                    "send": config.env._("Send"), "see": config.env._("See it"),
                },
            }).replace("</", "<\\/")),
        })
