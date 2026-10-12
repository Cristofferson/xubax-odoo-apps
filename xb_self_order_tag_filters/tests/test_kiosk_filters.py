# -*- coding: utf-8 -*-
from odoo.tests import tagged

from odoo.addons.pos_self_order.tests.self_order_common_test import SelfOrderCommonTest


@tagged("post_install", "-at_install")
class TestKioskFilters(SelfOrderCommonTest):

    def setUp(self):
        super().setUp()
        self.group = self.env["product.tag.group"].create({"name": "Style", "xb_kiosk_single": True})
        self.tag = self.env["product.tag"].create({
            "name": "Solitaire", "filter_group_id": self.group.id, "color": "#C99A45"})
        self.plain = self.env["product.tag"].create({"name": "Plain", "filter_group_id": self.group.id})
        self.pos_config.write({
            "self_ordering_mode": "kiosk",
            "xb_tf_layout": "dots",
            "xb_tf_icons": "jewelry",
            "xb_tf_show_count": False,
            "xb_tf_color_ink": "#14110E",
        })

    def test_settings_reach_the_kiosk(self):
        data = self.env["pos.config"]._load_pos_self_data_read(self.pos_config, self.pos_config)
        self.assertEqual(data[0]["_xb_tf"], {
            "layout": "dots", "icons": "jewelry", "show_count": False, "categ_ids": [],
            "ink": "#14110E", "accent": False,
        })

    def test_tag_group_and_color(self):
        tags = self.tag | self.plain
        data = {r["id"]: r for r in self.env["product.tag"]._load_pos_self_data_read(
            tags, self.pos_config)}
        self.assertEqual(data[self.tag.id]["_xb_color"], "#C99A45")
        self.assertFalse(data[self.plain.id]["_xb_color"], "Odoo's default color is not a choice")
        self.assertTrue(data[self.tag.id]["_xb_group"]["single"])

    def test_section_single_by_default(self):
        Category = self.env["product.public.category"]
        metal = Category.create({"name": "Rings", "xb_kiosk_filter_title": "Metal"})
        gold = Category.create({"name": "Yellow gold", "parent_id": metal.id})
        tmpl = self.cola.product_tmpl_id
        tmpl.public_categ_ids = [(6, 0, gold.ids)]
        read = self.env["product.template"]._load_pos_self_data_read(tmpl, self.pos_config)
        section = read[0]["_xb_sections"][0]
        self.assertEqual(section["group"]["name"], "Metal")
        self.assertTrue(section["group"]["single"])
        metal.xb_kiosk_filter_multi = True
        read = self.env["product.template"]._load_pos_self_data_read(tmpl, self.pos_config)
        self.assertFalse(read[0]["_xb_sections"][0]["group"]["single"])
