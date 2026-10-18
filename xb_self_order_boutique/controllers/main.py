# -*- coding: utf-8 -*-
import base64
import io
import json

from PIL import Image

from odoo import http
from odoo.http import request
from odoo.tools.image import image_process

from odoo.addons.pos_self_order.controllers.self_entry import PosSelfKiosk

SERVICE_WORKER = """// XUBAX - lets the browser install the kiosk as an app (it needs a fetch handler).
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (event) => {
    if (event.request.mode === "navigate") {
        event.respondWith(fetch(event.request));
    }
});
"""


class XbBoutiqueKiosk(PosSelfKiosk):

    def _xb_bq_app_config(self, config_id, access_token):
        pos_config, _, _ = self._verify_entry_access(str(config_id), access_token)
        pos_config = pos_config.sudo()
        if not (pos_config.xb_bq_enabled and pos_config.xb_bq_app):
            raise request.not_found()
        return pos_config

    @http.route("/xb-boutique/<int:config_id>/manifest.webmanifest", auth="public",
                type="http", sitemap=False)
    def xb_bq_manifest(self, config_id, access_token=None):
        """Web app manifest: the tablet can install the kiosk and open it full screen."""
        config = self._xb_bq_app_config(config_id, access_token)
        name = config.xb_bq_app_name or config.company_id.name
        bar = config.xb_bq_bar_color or "#FFFFFF"
        icon = "/xb-boutique/%s/icon-%%s.png?access_token=%s" % (config.id, access_token)
        manifest = {
            "name": name,
            "short_name": name[:12],
            "start_url": "/pos-self/%s?access_token=%s" % (config.id, access_token),
            "scope": "/pos-self/",
            "id": "/pos-self/%s" % config.id,
            "display": "fullscreen",
            "orientation": "portrait",
            "background_color": bar,
            "theme_color": bar,
            "icons": [
                {"src": icon % size, "sizes": "%sx%s" % (size, size), "type": "image/png",
                 "purpose": "any maskable"}
                for size in (192, 512)
            ],
        }
        return request.make_response(json.dumps(manifest), headers=[
            ("Content-Type", "application/manifest+json"),
            ("Cache-Control", "no-cache"),
        ])

    @http.route("/xb-boutique/<int:config_id>/icon-<int:size>.png", auth="public",
                type="http", sitemap=False)
    def xb_bq_icon(self, config_id, size, access_token=None):
        """The app icon: the one set on the kiosk, else the company logo, on a square."""
        config = self._xb_bq_app_config(config_id, access_token)
        size = 512 if size > 192 else 192
        source = config.xb_bq_app_icon or config.company_id.logo
        if not source:
            raise request.not_found()
        # A square icon is cut to size; a wide logo is shrunk whole onto a square.
        if config.xb_bq_app_icon:
            png = image_process(base64.b64decode(source), size=(size, size), crop="center",
                                output_format="PNG")
        else:
            logo = Image.open(io.BytesIO(base64.b64decode(source))).convert("RGBA")
            logo.thumbnail((int(size * 0.8), int(size * 0.8)), Image.LANCZOS)
            square = Image.new("RGBA", (size, size), (255, 255, 255, 0))
            square.paste(logo, ((size - logo.width) // 2, (size - logo.height) // 2), logo)
            out = io.BytesIO()
            square.save(out, "PNG")
            png = out.getvalue()
        return request.make_response(png, headers=[
            ("Content-Type", "image/png"),
            ("Cache-Control", "public, max-age=3600"),
        ])

    @http.route("/xb-boutique/sw.js", auth="public", type="http", sitemap=False)
    def xb_bq_service_worker(self):
        return request.make_response(SERVICE_WORKER, headers=[
            ("Content-Type", "text/javascript"),
            ("Service-Worker-Allowed", "/pos-self/"),
            ("Cache-Control", "no-cache"),
        ])
