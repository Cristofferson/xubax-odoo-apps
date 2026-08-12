# -*- coding: utf-8 -*-
import base64
import io
import logging
import re

from PIL import Image

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Only plain CSS colors are accepted: the value ends up as the value of a CSS
# custom property in the browser, so it is kept to a shape that cannot carry
# anything else.
COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

MAX_DARKENING = 80


class PosConfig(models.Model):
    _inherit = "pos.config"

    xb_bg_image = fields.Image(
        string="POS Background Image",
        max_width=1920,
        max_height=1920,
        help="Image shown behind the clock on the standby screen and on the "
             "cashier login screen of this Point of Sale, in place of the "
             "default Odoo background.",
    )
    xb_bg_image_name = fields.Char(string="POS Background Image Name")
    xb_bg_color = fields.Char(
        string="POS Background Color",
        help="Color painted behind the image. It is what shows through when "
             "the image does not cover the whole screen, and it replaces the "
             "background on its own when no image is set.",
    )
    xb_bg_fit = fields.Selection(
        selection=[
            ("cover", "Fill the screen"),
            ("contain", "Fit the whole image"),
            ("tile", "Tile"),
            ("center", "Center"),
        ],
        string="Image Fit",
        default="cover",
        required=True,
    )
    xb_bg_darkening = fields.Integer(
        string="Darkening (%)",
        default=0,
        help="Percentage of black laid over the image so the clock and the "
             "buttons stay readable on light or busy pictures. 0 leaves the "
             "image untouched.",
    )
    xb_bg_text = fields.Selection(
        selection=[
            ("auto", "Automatic"),
            ("dark", "Dark text"),
            ("light", "Light text"),
        ],
        string="Clock",
        default="auto",
        required=True,
        help="Color of the clock and the date drawn over the background. Odoo "
             "writes them in dark gray, which disappears on a dark picture. "
             "Automatic looks at how dark the background ends up — image, "
             "color and darkening together — and picks the readable one.",
    )
    xb_bg_is_dark = fields.Boolean(
        string="Background Is Dark",
        compute="_compute_xb_bg_is_dark",
        store=True,
        help="Technical: result of the Automatic reading of the background.",
    )
    xb_logo_source = fields.Selection(
        selection=[
            ("default", "Odoo logo"),
            ("company", "Company logo"),
            ("custom", "Custom logo"),
        ],
        string="POS Logo",
        default="default",
        required=True,
        help="Logo shown on the standby screen and in the middle of the POS "
             "top bar.",
    )
    xb_logo = fields.Image(
        string="Custom POS Logo",
        max_width=1024,
        max_height=1024,
        help="Used when the POS logo is set to Custom. A transparent PNG or an "
             "SVG gives the best result, since the logo is drawn straight over "
             "the background.",
    )
    xb_logo_name = fields.Char(string="Custom POS Logo Name")

    @api.constrains("xb_bg_color")
    def _check_xb_bg_color(self):
        for config in self:
            if config.xb_bg_color and not COLOR_RE.match(config.xb_bg_color.strip()):
                raise ValidationError(_(
                    "The Point of Sale background color must be a hexadecimal "
                    "color such as #1B2A4A."
                ))

    @api.constrains("xb_bg_darkening")
    def _check_xb_bg_darkening(self):
        for config in self:
            if not 0 <= config.xb_bg_darkening <= MAX_DARKENING:
                raise ValidationError(_(
                    "The Point of Sale background darkening must be between 0 "
                    "and %s percent.", MAX_DARKENING,
                ))

    # --- Automatic clock color -------------------------------------------

    def _xb_color_luminance(self, color):
        """Perceived brightness of a #rrggbb color, from 0 (black) to 1."""
        value = color.strip().lstrip("#")
        if len(value) in (3, 4):
            value = "".join(c * 2 for c in value[:3])
        red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
        return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255

    def _xb_bg_image_luminance(self, data, color):
        """Perceived brightness of the uploaded picture, from 0 to 1.

        The image is read down to 16x16 first: that is enough to tell a night
        photograph from a white studio shot, and it keeps the whole reading
        under a millisecond.
        """
        image = Image.open(io.BytesIO(base64.b64decode(data)))
        image = image.resize((16, 16))
        if image.mode in ("RGBA", "LA", "P"):
            image = image.convert("RGBA")
            # Transparent pictures let the background color through, so that
            # is what they have to be read against.
            behind = "#FFFFFF"
            if color and COLOR_RE.match(color.strip()):
                behind = color.strip()
            value = behind.lstrip("#")
            if len(value) in (3, 4):
                value = "".join(c * 2 for c in value[:3])
            canvas = Image.new("RGBA", image.size, tuple(
                int(value[i:i + 2], 16) for i in (0, 2, 4)
            ) + (255,))
            image = Image.alpha_composite(canvas, image)
        pixels = list(image.convert("RGB").getdata())
        total = sum(
            0.2126 * red + 0.7152 * green + 0.0722 * blue
            for red, green, blue in pixels
        )
        return total / (len(pixels) * 255)

    @api.depends("xb_bg_image", "xb_bg_color", "xb_bg_darkening")
    def _compute_xb_bg_is_dark(self):
        for config in self:
            luminance = None
            try:
                if config.xb_bg_image:
                    luminance = self._xb_bg_image_luminance(
                        config.xb_bg_image, config.xb_bg_color
                    )
                elif config.xb_bg_color:
                    luminance = self._xb_color_luminance(config.xb_bg_color)
            except Exception:
                # A background that cannot be read is not worth a traceback in
                # the middle of saving the POS settings: fall back to Odoo's
                # own light background, which is what is on screen anyway.
                _logger.warning(
                    "Could not read the brightness of the background of POS %s",
                    config.display_name, exc_info=True,
                )
            if luminance is None:
                config.xb_bg_is_dark = False
                continue
            darkening = min(max(config.xb_bg_darkening or 0, 0), MAX_DARKENING)
            config.xb_bg_is_dark = luminance * (1 - darkening / 100) < 0.5

    def _xb_uses_light_text(self, config):
        if config.xb_bg_text == "light":
            return True
        if config.xb_bg_text == "dark":
            return False
        return config.xb_bg_is_dark

    # --- Serving the images ----------------------------------------------

    def _xb_image_token(self, model, record_id, field_name, fallback):
        """Cache-busting token for an image served through ``/web/image``.

        Odoo keeps image fields in ``ir.attachment``, whose checksum changes
        when — and only when — the picture itself changes. Using it means the
        terminals pick up a new background on their next load, and that they do
        *not* re-download it every time an unrelated setting of the same Point
        of Sale is saved.
        """
        attachment = self.env["ir.attachment"].sudo().search([
            ("res_model", "=", model),
            ("res_id", "=", record_id),
            ("res_field", "=", field_name),
        ], limit=1)
        if attachment.checksum:
            return attachment.checksum
        return fallback.strftime("%Y%m%d%H%M%S%f") if fallback else "0"

    def _xb_image_url(self, model, record_id, field_name, token):
        """URL of a stored image.

        The bytes travel over ``/web/image`` — which honours the reader's
        access rights — instead of the POS loading payload, so the browser
        downloads them once and then serves them from its own cache.
        """
        return f"/web/image/{model}/{record_id}/{field_name}?unique={token}"

    @api.model
    def _load_pos_data_read(self, records, config):
        read_records = super()._load_pos_data_read(records, config)
        if not read_records:
            return read_records

        record = read_records[0]

        # pos.config._load_pos_data_fields() returns [] — the POS reads *every*
        # stored field — so an untouched fields.Image would be shipped base64
        # in the loading payload of every terminal, every session. Both images
        # are dropped from the payload here and sent as URLs instead.
        record["xb_bg_image"] = False
        record["xb_logo"] = False

        record["_xb_bg_url"] = (
            self._xb_config_image_url(config, "xb_bg_image")
            if config.xb_bg_image else False
        )

        logo_url = False
        if config.xb_logo_source == "custom" and config.xb_logo:
            logo_url = self._xb_config_image_url(config, "xb_logo")
        elif config.xb_logo_source == "company" and config.company_id.logo:
            # res.company.logo is related to partner_id.image_1920, so that is
            # where the attachment — and the checksum — actually lives.
            company = config.company_id
            token = self._xb_image_token(
                "res.partner", company.partner_id.id, "image_1920", company.write_date
            )
            logo_url = self._xb_image_url("res.company", company.id, "logo", token)
        record["_xb_logo_url"] = logo_url
        record["_xb_light_text"] = self._xb_uses_light_text(config)

        return read_records

    def _xb_config_image_url(self, config, field_name):
        token = self._xb_image_token(
            "pos.config", config.id, field_name, config.write_date
        )
        return self._xb_image_url("pos.config", config.id, field_name, token)
