# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")

TITLE_FONTS = [
    ("cormorant", "Cormorant Garamond (elegant serif)"),
    ("playfair", "Playfair Display (classic serif)"),
    ("montserrat", "Montserrat (geometric sans)"),
    ("serif", "Device serif"),
    ("sans", "Device sans-serif"),
]
BODY_FONTS = [
    ("jost", "Jost"),
    ("lato", "Lato"),
    ("montserrat", "Montserrat"),
    ("sans", "Device sans-serif"),
]
COLOR_FIELDS = ("xb_bq_color_primary", "xb_bq_color_ink", "xb_bq_color_photo", "xb_bq_color_line")
TEXT_FIELDS = {
    "checkout": "xb_bq_txt_checkout",
    "order": "xb_bq_txt_order",
    "cart_title": "xb_bq_txt_cart_title",
    "done": "xb_bq_txt_done",
    "number": "xb_bq_txt_number",
    "from": "xb_bq_txt_from",
}


class PosConfig(models.Model):
    _inherit = "pos.config"

    xb_bq_enabled = fields.Boolean(
        string="Boutique Theme",
        help="The kiosk takes the look of a boutique: large photos, your colors and fonts, "
             "shop words on the buttons.")
    xb_bq_color_primary = fields.Char(
        string="Boutique: Main Color", default="#A6824C",
        help="Buttons, the active category and the chosen options.")
    xb_bq_color_ink = fields.Char(
        string="Boutique: Text Color", default="#14110E",
        help="Product names, prices and titles.")
    xb_bq_color_photo = fields.Char(
        string="Boutique: Photo Background", default="#F1EFEB",
        help="Behind every product photo. Photos on white blend into it.")
    xb_bq_color_line = fields.Char(
        string="Boutique: Line Color", default="#E6E1D9",
        help="Thin lines and the frame of the options.")
    xb_bq_font_title = fields.Selection(
        TITLE_FONTS, string="Boutique: Title Font", default="cormorant", required=True)
    xb_bq_font_body = fields.Selection(
        BODY_FONTS, string="Boutique: Text Font", default="jost", required=True)
    xb_bq_corners = fields.Selection(
        [("square", "Square"), ("rounded", "Rounded")],
        string="Boutique: Corners", default="square", required=True)
    xb_bq_columns = fields.Selection(
        [("2", "2"), ("3", "3"), ("4", "4")],
        string="Boutique: Product Columns", default="2", required=True,
        help="Columns of the product list on a portrait tablet. Wide screens add one.")
    xb_bq_price = fields.Selection(
        [("price", "Price"), ("from", "\"From\" + price"), ("none", "No price")],
        string="Boutique: Price in the List", default="from", required=True,
        help="\"From\" + price: products with options that change the price show the lowest "
             "one after \"From\". No price: the price shows only on the product page.")
    xb_bq_gallery = fields.Selection(
        [("single", "Main photo"), ("carousel", "Carousel"), ("mosaic", "Mosaic with video")],
        string="Boutique: Product Gallery", default="mosaic", required=True,
        help="What the product page shows: the main photo, a carousel of the extra photos "
             "(swipe), or a mosaic with the published video on top and the photos two by two.")
    xb_bq_txt_checkout = fields.Char(
        string="Boutique: Product List Button", translate=True,
        help="Empty: \"View my selection\".")
    xb_bq_txt_order = fields.Char(
        string="Boutique: Cart Button", translate=True,
        help="Empty: \"Pay at the counter\".")
    xb_bq_txt_cart_title = fields.Char(
        string="Boutique: Cart Title", translate=True,
        help="Empty: \"Your selection\".")
    xb_bq_txt_done = fields.Char(
        string="Boutique: Confirmation Title", translate=True,
        help="Empty: \"All set! See you at the counter\".")
    xb_bq_txt_number = fields.Char(
        string="Boutique: Order Number Title", translate=True,
        help="Empty: \"Your order number\".")
    xb_bq_txt_from = fields.Char(
        string="Boutique: \"From\" Word", translate=True,
        help="Empty: \"From\".")
    xb_bq_app = fields.Boolean(
        string="Boutique: Installable App",
        help="The tablet can install the kiosk as an app that opens full screen, with your "
             "name and icon. In a plain browser tab, the first touch switches to full screen.")
    xb_bq_app_name = fields.Char(
        string="Boutique: App Name", help="Empty: the company name.")
    xb_bq_app_icon = fields.Image(
        string="Boutique: App Icon", max_width=512, max_height=512,
        help="Square image, at least 512 x 512 px. Empty: the company logo.")
    xb_bq_bar_color = fields.Char(
        string="Boutique: Bar Color", default="#FFFFFF",
        help="Color of the tablet's status bar and of the app's splash screen.")

    @api.constrains(*COLOR_FIELDS, "xb_bq_bar_color")
    def _check_xb_bq_colors(self):
        for config in self:
            for name in COLOR_FIELDS + ("xb_bq_bar_color",):
                value = config[name]
                if value and not HEX_COLOR.match(value):
                    raise ValidationError(_(
                        "%(field)s must be a color like #A6824C.",
                        field=config._fields[name].string))

    def _xb_bq_settings(self):
        """What the kiosk page needs to dress itself; False when the theme is off."""
        self.ensure_one()
        if not self.xb_bq_enabled:
            return False
        return {
            "primary": self.xb_bq_color_primary or "#A6824C",
            "ink": self.xb_bq_color_ink or "#14110E",
            "photo": self.xb_bq_color_photo or "#F1EFEB",
            "line": self.xb_bq_color_line or "#E6E1D9",
            "font_title": self.xb_bq_font_title or "cormorant",
            "font_body": self.xb_bq_font_body or "jost",
            "corners": self.xb_bq_corners or "square",
            "columns": int(self.xb_bq_columns or 2),
            "price": self.xb_bq_price or "from",
            "gallery": self.xb_bq_gallery or "mosaic",
            "app": self.xb_bq_app,
            "texts": {key: self[name] or False for key, name in TEXT_FIELDS.items()},
        }

    def _xb_bq_media_wanted(self):
        self.ensure_one()
        return bool(self.xb_bq_enabled and self.xb_bq_gallery in ("carousel", "mosaic"))

    @api.model
    def _load_pos_self_data_read(self, records, config):
        read_records = super()._load_pos_self_data_read(records, config)
        if read_records:
            read_records[0]["_xb_bq"] = config.sudo()._xb_bq_settings()
        return read_records
