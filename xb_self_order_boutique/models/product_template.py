# -*- coding: utf-8 -*-
from odoo import models

# Every playable copy of the video, best first (webm plays where H.264 is missing).
VIDEO_ORDER = ("video/webm", "video/mp4")


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _load_pos_self_data_read(self, data, config):
        """With the carousel or the mosaic, each product carries its gallery: the extra
        photos and the published video (the same ones the website shows)."""
        res = super()._load_pos_self_data_read(data, config)
        ids = [r["id"] for r in res]
        if not ids or not config._xb_bq_media_wanted():
            return res
        photos = {}
        # Extra photos exist only with the online shop (website_sale) installed.
        images = self.env["product.image"].sudo().search(
            [("product_tmpl_id", "in", ids)], order="sequence, id"
        ) if "product.image" in self.env else []
        for img in images:
            photos.setdefault(img.product_tmpl_id.id, []).append(
                "/web/image/product.image/%s/image_1024" % img.id
            )
        videos = {}
        for att in self.env["ir.attachment"].sudo().search([
            ("res_model", "=", "product.template"), ("res_id", "in", ids),
            ("mimetype", "in", VIDEO_ORDER), ("public", "=", True), ("res_field", "=", False),
        ], order="id desc"):
            sources = videos.setdefault(att.res_id, {})
            sources.setdefault(att.mimetype, "/web/content/%s" % att.id)
        for r in res:
            v = videos.get(r["id"], {})
            r["_xb_bq_media"] = {
                "photos": photos.get(r["id"], []),
                "video": [{"url": v[m], "type": m} for m in VIDEO_ORDER if m in v],
            }
        return res
