# -*- coding: utf-8 -*-
from odoo import models


class PosConfig(models.Model):
    _inherit = "pos.config"

    def _xb_kiosk_whatsapp_ready(self):
        """WhatsApp when a Point of Sale of the company has its approved quotation
        template: the kiosk sends with that same template."""
        self.ensure_one()
        return bool(self.env["pos.config"].sudo().search([
            ("company_id", "=", self.company_id.id),
            ("xb_quotation_wa_template_id.status", "=", "approved"),
        ], limit=1))
