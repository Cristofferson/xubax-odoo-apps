# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    xb_kiosk_quotation = fields.Boolean(
        string="Quotations from the kiosk",
        help="In the kiosk cart the customer can ask for a quotation, printed on the "
             "kiosk's receipt printer and/or sent to their WhatsApp.")
    xb_kiosk_privacy_url = fields.Char(
        string="Privacy notice",
        help="Page with your privacy notice, linked when the customer leaves their "
             "name and mobile. Empty: the customer only agrees to be contacted.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("xb_kiosk_quotation"):
                vals.setdefault("xb_enable_sale_order", True)
        return super().create(vals_list)

    def write(self, vals):
        # Kiosk quotations are made like the POS ones: that feature must be on.
        if vals.get("xb_kiosk_quotation"):
            vals = dict(vals, xb_enable_sale_order=True)
        return super().write(vals)

    def _xb_kiosk_quotation_modes(self):
        """How this kiosk can hand over a quotation: printed and/or by WhatsApp."""
        self.ensure_one()
        config = self.sudo()
        if (config.self_ordering_mode != "kiosk" or not config.xb_kiosk_quotation
                or not config.xb_enable_sale_order):
            return {"print": False, "whatsapp": False, "privacy_url": False}
        whatsapp = bool(self.env["pos.config"].sudo().search([
            ("company_id", "=", config.company_id.id),
            ("xb_quotation_wa_template_id.status", "=", "approved"),
        ], limit=1))
        return {
            "print": bool(config.other_devices and config.epson_printer_ip),
            "whatsapp": whatsapp,
            "privacy_url": config.xb_kiosk_privacy_url or False,
        }

    @api.model
    def _load_pos_self_data_read(self, records, config):
        read_records = super()._load_pos_self_data_read(records, config)
        if read_records:
            read_records[0]["_xb_quotation"] = config._xb_kiosk_quotation_modes()
        return read_records
