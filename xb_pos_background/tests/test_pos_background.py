# -*- coding: utf-8 -*-

from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

# Two single-pixel PNGs. They differ, which is what lets the cache-busting
# token be tested: the token is the checksum of the stored attachment.
RED_PIXEL = (
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/"
    b"iZk9HQAAAABJRU5ErkJggg=="
)
BLUE_PIXEL = (
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYPj/HwADAgH/"
    b"5ncLrgAAAABJRU5ErkJggg=="
)
# A night-dark and a daylight-bright 8x8 image, for the automatic clock color.
BLACK_IMAGE = (
    b"iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAFUlEQVR4nGPkERD7z4AHMOGT"
    b"HD4KAD91AUHZlbPOAAAAAElFTkSuQmCC"
)
WHITE_IMAGE = (
    b"iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAFklEQVR4nGP89uXDfwY8gAmf"
    b"5PBRAAD3kwPpvA072gAAAABJRU5ErkJggg=="
)


@tagged("post_install", "-at_install")
class TestPosBackground(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env["pos.config"].search([], limit=1)
        if not cls.config:
            cls.config = cls.env["pos.config"].create({"name": "XB Background Test"})

    def _payload(self):
        """The pos.config record as the Point of Sale receives it."""
        return self.env["pos.config"]._load_pos_data_read(self.config, self.config)[0]

    # --- Defaults: an untouched Point of Sale must look like a plain Odoo ---

    def test_defaults_change_nothing(self):
        fresh = self.env["pos.config"].new({"name": "XB Untouched"})
        self.assertFalse(fresh.xb_bg_image)
        self.assertFalse(fresh.xb_bg_color)
        self.assertEqual(fresh.xb_bg_fit, "cover")
        self.assertEqual(fresh.xb_bg_darkening, 0)
        self.assertEqual(fresh.xb_bg_text, "auto")
        self.assertEqual(fresh.xb_logo_source, "default")

        self.config.write({
            "xb_bg_image": False,
            "xb_bg_color": False,
            "xb_bg_darkening": 0,
            "xb_logo_source": "default",
        })
        payload = self._payload()
        self.assertFalse(payload["_xb_bg_url"])
        self.assertFalse(payload["_xb_logo_url"])
        self.assertFalse(payload["_xb_light_text"])

    # --- The images must not be shipped inside the POS loading payload ---

    def test_images_are_not_sent_base64(self):
        """pos.config._load_pos_data_fields() is [], so every stored field is
        read: both images have to be stripped from the payload by hand."""
        self.config.write({
            "xb_bg_image": RED_PIXEL,
            "xb_logo_source": "custom",
            "xb_logo": RED_PIXEL,
        })
        payload = self._payload()
        self.assertFalse(payload["xb_bg_image"])
        self.assertFalse(payload["xb_logo"])
        # ... and no other key smuggles the bytes in.
        for key, value in payload.items():
            if isinstance(value, bytes):
                self.fail(f"{key} carries raw bytes into the POS payload")

    def test_background_url_points_at_the_image(self):
        self.config.write({"xb_bg_image": RED_PIXEL})
        url = self._payload()["_xb_bg_url"]
        self.assertTrue(url.startswith(
            f"/web/image/pos.config/{self.config.id}/xb_bg_image?unique="
        ), url)

    def test_url_changes_when_the_image_changes(self):
        self.config.write({"xb_bg_image": RED_PIXEL})
        first = self._payload()["_xb_bg_url"]
        self.config.write({"xb_bg_image": BLUE_PIXEL})
        self.assertNotEqual(first, self._payload()["_xb_bg_url"])

    def test_url_survives_an_unrelated_setting(self):
        """Saving any other POS setting must not force every terminal to
        download the background again."""
        self.config.write({"xb_bg_image": RED_PIXEL})
        first = self._payload()["_xb_bg_url"]
        self.config.write({"xb_bg_darkening": 25})
        self.assertEqual(first, self._payload()["_xb_bg_url"])

    # --- Logo source ---

    def test_logo_source_company(self):
        self.config.company_id.logo = RED_PIXEL
        self.config.write({"xb_logo_source": "company"})
        url = self._payload()["_xb_logo_url"]
        self.assertTrue(url.startswith(
            f"/web/image/res.company/{self.config.company_id.id}/logo?unique="
        ), url)

    def test_logo_source_custom(self):
        self.config.write({"xb_logo_source": "custom", "xb_logo": RED_PIXEL})
        url = self._payload()["_xb_logo_url"]
        self.assertTrue(url.startswith(
            f"/web/image/pos.config/{self.config.id}/xb_logo?unique="
        ), url)

    def test_logo_source_custom_without_image(self):
        """Picking Custom and uploading nothing must fall back to Odoo's logo,
        not to a broken image."""
        self.config.write({"xb_logo_source": "custom", "xb_logo": False})
        self.assertFalse(self._payload()["_xb_logo_url"])

    def test_logo_source_default_ignores_a_stored_logo(self):
        self.config.write({"xb_logo": RED_PIXEL, "xb_logo_source": "default"})
        self.assertFalse(self._payload()["_xb_logo_url"])

    # --- The clock has to stay readable over the background ---

    def test_clock_stays_dark_on_a_plain_odoo(self):
        self.config.write({"xb_bg_image": False, "xb_bg_color": False})
        self.assertFalse(self._payload()["_xb_light_text"])

    def test_clock_turns_white_on_a_dark_color(self):
        self.config.write({"xb_bg_image": False, "xb_bg_color": "#101820"})
        self.assertTrue(self._payload()["_xb_light_text"])

    def test_clock_stays_dark_on_a_light_color(self):
        self.config.write({"xb_bg_image": False, "xb_bg_color": "#F5F1E8"})
        self.assertFalse(self._payload()["_xb_light_text"])

    def test_clock_turns_white_on_a_dark_image(self):
        self.config.write({"xb_bg_image": BLACK_IMAGE, "xb_bg_darkening": 0})
        self.assertTrue(self._payload()["_xb_light_text"])

    def test_clock_stays_dark_on_a_light_image(self):
        self.config.write({"xb_bg_image": WHITE_IMAGE, "xb_bg_darkening": 0})
        self.assertFalse(self._payload()["_xb_light_text"])

    def test_darkening_can_turn_a_light_image_dark(self):
        """A bright photo under a heavy veil ends up dark, and the clock has to
        follow — this is the case a plain look at the image would get wrong."""
        self.config.write({"xb_bg_image": WHITE_IMAGE, "xb_bg_darkening": 0})
        self.assertFalse(self._payload()["_xb_light_text"])
        self.config.write({"xb_bg_darkening": 60})
        self.assertTrue(self._payload()["_xb_light_text"])

    def test_clock_color_can_be_forced(self):
        self.config.write({"xb_bg_image": WHITE_IMAGE, "xb_bg_darkening": 0})
        self.config.xb_bg_text = "light"
        self.assertTrue(self._payload()["_xb_light_text"])
        self.config.xb_bg_text = "dark"
        self.config.xb_bg_image = BLACK_IMAGE
        self.assertFalse(self._payload()["_xb_light_text"])

    def test_a_background_that_cannot_be_read_is_treated_as_light(self):
        """A picture Odoo cannot open — a filestore file gone missing, say —
        must not bring down the saving of the POS settings: the screen simply
        keeps Odoo's own colors."""
        with patch.object(
            type(self.config), "_xb_bg_image_luminance", side_effect=ValueError("boom")
        ):
            self.config.write({"xb_bg_image": BLACK_IMAGE})
            self.config.flush_recordset()
        self.assertFalse(self.config.xb_bg_is_dark)

    # --- Constraints: the color ends up in a CSS custom property ---

    def test_color_accepts_hexadecimal(self):
        for color in ("#000", "#1B2A4A", "#1b2a4aff"):
            self.config.xb_bg_color = color
            self.assertEqual(self.config.xb_bg_color, color)

    def test_color_rejects_anything_else(self):
        for color in ("red", "url(x)", "#12", "rgb(1,2,3)", "#fff; background: red"):
            with self.assertRaises(ValidationError, msg=color):
                self.config.xb_bg_color = color
                self.config.flush_recordset()

    def test_darkening_is_bounded(self):
        for value in (-1, 81, 1000):
            with self.assertRaises(ValidationError, msg=str(value)):
                self.config.xb_bg_darkening = value
                self.config.flush_recordset()

    def test_darkening_accepts_the_whole_range(self):
        for value in (0, 40, 80):
            self.config.xb_bg_darkening = value
            self.config.flush_recordset()
            self.assertEqual(self.config.xb_bg_darkening, value)

    # --- The settings page writes back to the selected Point of Sale ---

    def test_settings_write_back_to_the_config(self):
        settings = self.env["res.config.settings"].create({
            "pos_config_id": self.config.id,
            "pos_xb_bg_color": "#123456",
            "pos_xb_bg_fit": "tile",
            "pos_xb_bg_darkening": 35,
            "pos_xb_logo_source": "company",
        })
        settings.execute()
        self.assertEqual(self.config.xb_bg_color, "#123456")
        self.assertEqual(self.config.xb_bg_fit, "tile")
        self.assertEqual(self.config.xb_bg_darkening, 35)
        self.assertEqual(self.config.xb_logo_source, "company")

    # --- A cashier must be able to fetch the image ---

    def test_cashier_can_read_the_background(self):
        cashier = self.env["res.users"].create({
            "name": "XB Test Cashier",
            "login": "xb_test_cashier",
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("point_of_sale.group_pos_user").id,
            ])],
        })
        self.config.write({"xb_bg_image": RED_PIXEL})
        # /web/image checks read access on the record, which POS users have.
        self.assertTrue(
            self.config.with_user(cashier).read(["xb_bg_image"])[0]["xb_bg_image"]
        )
