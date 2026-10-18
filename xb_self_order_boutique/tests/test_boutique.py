# -*- coding: utf-8 -*-
import base64
import io

from PIL import Image

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.pos_self_order.tests.self_order_common_test import SelfOrderCommonTest


def _png(width, height):
    out = io.BytesIO()
    Image.new("RGB", (width, height), (166, 130, 76)).save(out, "PNG")
    return base64.b64encode(out.getvalue())


@tagged("post_install", "-at_install")
class TestKioskBoutique(SelfOrderCommonTest):

    def setUp(self):
        super().setUp()
        self.pos_config.write({"self_ordering_mode": "kiosk"})
        self.product = self.cola.product_tmpl_id

    def _kiosk_data(self):
        return self.pos_config.load_self_data()

    def test_off_by_default(self):
        """Without the theme, the kiosk gets nothing new."""
        data = self._kiosk_data()
        self.assertFalse(data["pos.config"][0]["_xb_bq"])
        row = next(r for r in data["product.template"] if r["id"] == self.product.id)
        self.assertNotIn("_xb_bq_media", row)

    def test_settings_reach_the_kiosk(self):
        self.pos_config.write({
            "xb_bq_enabled": True,
            "xb_bq_color_primary": "#1F6F5C",
            "xb_bq_font_title": "playfair",
            "xb_bq_columns": "3",
            "xb_bq_price": "price",
            "xb_bq_txt_order": "Pay at the desk",
        })
        bq = self._kiosk_data()["pos.config"][0]["_xb_bq"]
        self.assertEqual(bq["primary"], "#1F6F5C")
        self.assertEqual(bq["font_title"], "playfair")
        self.assertEqual(bq["columns"], 3)
        self.assertEqual(bq["price"], "price")
        self.assertEqual(bq["texts"]["order"], "Pay at the desk")
        self.assertFalse(bq["texts"]["checkout"], "Empty words fall back to the theme's own.")

    def test_gallery_media(self):
        """Carousel and mosaic bring the extra photos and the public video; the main photo does not."""
        shop = "product.image" in self.env
        if shop:
            self.env["product.image"].create({
                "name": "Back", "product_tmpl_id": self.product.id, "image_1920": _png(64, 64)})
        self.env["ir.attachment"].create({
            "name": "spin.webm", "res_model": "product.template", "res_id": self.product.id,
            "mimetype": "video/webm", "public": True, "raw": b"\x1aE\xdf\xa3 webm"})
        self.pos_config.write({"xb_bq_enabled": True, "xb_bq_gallery": "mosaic"})
        row = next(r for r in self._kiosk_data()["product.template"] if r["id"] == self.product.id)
        self.assertEqual(len(row["_xb_bq_media"]["photos"]), 1 if shop else 0)
        self.assertEqual(row["_xb_bq_media"]["video"][0]["type"], "video/webm")
        self.pos_config.xb_bq_gallery = "single"
        row = next(r for r in self._kiosk_data()["product.template"] if r["id"] == self.product.id)
        self.assertNotIn("_xb_bq_media", row)

    def test_colors_are_checked(self):
        with self.assertRaises(ValidationError):
            self.pos_config.xb_bq_color_ink = "black"

    def test_installable_app(self):
        token = self.pos_config.access_token
        url = "/xb-boutique/%s/manifest.webmanifest?access_token=%s" % (self.pos_config.id, token)
        self.pos_config.write({"xb_bq_enabled": True})
        self.assertEqual(self.url_open(url).status_code, 404, "No app unless it is switched on.")
        self.pos_config.write({"xb_bq_app": True, "xb_bq_app_name": "Showroom",
                               "xb_bq_bar_color": "#14110E", "xb_bq_app_icon": _png(600, 600)})
        manifest = self.url_open(url).json()
        self.assertEqual(manifest["name"], "Showroom")
        self.assertEqual(manifest["theme_color"], "#14110E")
        self.assertEqual(manifest["display"], "fullscreen")
        icon = self.url_open(manifest["icons"][1]["src"])
        self.assertEqual(icon.headers["Content-Type"], "image/png")
        self.assertEqual(Image.open(io.BytesIO(icon.content)).size, (512, 512))
        bad = "/xb-boutique/%s/manifest.webmanifest?access_token=wrong" % self.pos_config.id
        self.assertNotEqual(self.url_open(bad).status_code, 200)

    def test_wide_logo_becomes_a_square_icon(self):
        self.env.company.logo = _png(400, 100)
        self.pos_config.write({"xb_bq_enabled": True, "xb_bq_app": True})
        url = "/xb-boutique/%s/icon-192.png?access_token=%s" % (
            self.pos_config.id, self.pos_config.access_token)
        icon = Image.open(io.BytesIO(self.url_open(url).content))
        self.assertEqual(icon.size, (192, 192))
