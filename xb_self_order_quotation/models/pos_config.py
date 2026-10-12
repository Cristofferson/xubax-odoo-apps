# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    xb_kiosk_quotation = fields.Boolean(
        string="Quotations from the kiosk",
        help="In the kiosk cart the customer can ask for a quotation, printed on the "
             "kiosk's receipt printer and/or sent to their WhatsApp.")
    xb_kiosk_counter_order = fields.Boolean(
        string="Pay at the counter through Sales",
        help="The kiosk's order button creates a quotation in Sales instead of a POS "
             "order: the cashier charges it from the POS quotations/orders list and it "
             "becomes a sales order, as with the POS quotations.")
    xb_kiosk_contact = fields.Selection(
        [("phone", "Mobile"), ("email", "Email"), ("both", "Mobile and email")],
        string="Ask the customer for", default="phone", required=True,
        help="What the kiosk asks for to save the quotation and find the customer again. "
             "With an email, the customer can also get the quotation by email.")
    xb_kiosk_privacy_url = fields.Char(
        string="Privacy notice",
        help="Page with your privacy notice, linked when the customer leaves their "
             "name and mobile. Empty: the customer only agrees to be contacted.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("xb_kiosk_quotation") or vals.get("xb_kiosk_counter_order"):
                vals.setdefault("xb_enable_sale_order", True)
        return super().create(vals_list)

    def write(self, vals):
        # Kiosk quotations are made like the POS ones: that feature must be on.
        if vals.get("xb_kiosk_quotation") or vals.get("xb_kiosk_counter_order"):
            vals = dict(vals, xb_enable_sale_order=True)
        return super().write(vals)

    def _xb_kiosk_quotation_modes(self):
        """How this kiosk can hand over a quotation: printed, by WhatsApp and/or by
        email, whether its order button sends the cart to the counter as a quotation,
        and what it asks the customer for (mobile, email or both)."""
        self.ensure_one()
        config = self.sudo()
        contact = config.xb_kiosk_contact or "phone"
        counter = bool(config.self_ordering_mode == "kiosk" and config.xb_kiosk_counter_order
                       and config.xb_enable_sale_order)
        printer = bool(config.other_devices and config.epson_printer_ip)
        if (config.self_ordering_mode != "kiosk" or not config.xb_kiosk_quotation
                or not config.xb_enable_sale_order):
            return {"print": False, "whatsapp": False, "email": False, "contact": contact,
                    "counter": counter, "counter_print": counter and printer,
                    "privacy_url": (counter and config.xb_kiosk_privacy_url) or False}
        # WhatsApp needs the mobile; the email delivery needs the email.
        whatsapp = contact != "email" and config._xb_kiosk_whatsapp_ready()
        return {
            "print": printer,
            "whatsapp": whatsapp,
            "email": contact != "phone",
            "contact": contact,
            "counter": counter,
            "counter_print": counter and printer,
            "privacy_url": config.xb_kiosk_privacy_url or False,
        }

    def _xb_kiosk_whatsapp_ready(self):
        """Whether the kiosk can send the quotation by WhatsApp. Never without the
        WhatsApp add-on (xb_self_order_quotation_whatsapp)."""
        return False

    @api.model
    def _load_pos_self_data_read(self, records, config):
        read_records = super()._load_pos_self_data_read(records, config)
        if read_records:
            read_records[0]["_xb_quotation"] = config._xb_kiosk_quotation_modes()
        return read_records
