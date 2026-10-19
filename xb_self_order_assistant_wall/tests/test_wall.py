# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.pos_self_order.tests.self_order_common_test import SelfOrderCommonTest
from odoo.addons.xb_showroom_wall_self_order.controllers.kiosk import ShowroomKiosk


@tagged("post_install", "-at_install")
class TestSellerWall(SelfOrderCommonTest):

    def test_push_through_the_kiosk_door(self):
        """With a wall, the seller offers it and sends the piece through the kiosk's own button logic."""
        self.pos_config.write({"self_ordering_mode": "kiosk", "xb_va_enabled": True})
        conv = self.env["xb.va.conversation"].create({"config_id": self.pos_config.id})
        PosConfig = type(self.pos_config)
        with patch.object(PosConfig, "_xb_showroom_kiosk_screen", lambda self: self.env["xb.showroom.screen"]):
            self.assertNotIn("mostrar_en_muro", [t["name"] for t in conv._xb_va_tools()])
        sent = {}

        def fake_push(ctrl, **kw):
            sent.update(kw)
            return {"ok": True, "message": "Look at the wall!"}

        product = self.cola.product_tmpl_id
        product.self_order_available = True
        with patch.object(PosConfig, "_xb_showroom_kiosk_screen", lambda self: self.env["xb.showroom.screen"].new({})), \
                patch.object(type(self.env["xb.va.conversation"]), "_xb_va_wall_push", lambda conv, tmpl, opts, mode: fake_push(None, template_id=tmpl.id, mode=mode, access_token=conv.config_id.access_token)):
            self.assertIn("mostrar_en_muro", [t["name"] for t in conv._xb_va_tools()])
            text, error = conv._xb_va_run_tool("mostrar_en_muro", {"producto_id": product.id, "comparar": True},
                                               conv._xb_va_new_ui())
        self.assertFalse(error, text)
        self.assertIn("Look at the wall!", text)
        self.assertEqual(sent["template_id"], product.id)
        self.assertEqual(sent["mode"], "compare")
        self.assertEqual(sent["access_token"], self.pos_config.access_token)
