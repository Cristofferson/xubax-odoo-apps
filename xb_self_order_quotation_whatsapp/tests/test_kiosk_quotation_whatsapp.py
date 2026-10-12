# -*- coding: utf-8 -*-
from odoo.tests import tagged

from odoo.addons.pos_self_order.tests.self_order_common_test import SelfOrderCommonTest


@tagged("post_install", "-at_install")
class TestKioskQuotationWhatsapp(SelfOrderCommonTest):

    def test_whatsapp_needs_approved_template(self):
        """No approved quotation template, no WhatsApp button on the kiosk."""
        self.pos_config.write({"self_ordering_mode": "kiosk", "xb_kiosk_quotation": True})
        self.assertFalse(self.pos_config._xb_kiosk_quotation_modes()["whatsapp"])
