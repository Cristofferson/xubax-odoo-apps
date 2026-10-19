# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields, models

from odoo.addons.xb_business_agent.models.whatsapp_account import xb_phone_key

# How recent a kiosk conversation must be for the WhatsApp agent to continue it.
KIOSK_DAYS = 3


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _xb_ba_context_text(self):
        """The WhatsApp agent knows what the customer talked about with the kiosk's virtual
        seller (same mobile number, last days): it continues that conversation."""
        text = super()._xb_ba_context_text()
        kiosk = self._xb_va_kiosk_conversation()
        if not kiosk:
            return text
        products = ", ".join("%s (%s)" % (t.name, kiosk._xb_va_price_label(t)) for t in kiosk.product_ids[:8])
        return "%s\nThis customer talked with %s, the shop's kiosk virtual seller, on %s. Continue THAT " \
               "conversation (do not repeat it or greet them as someone new).%s\nKiosk conversation:\n%s" % (
                   text, kiosk.config_id.xb_va_name or "the virtual seller",
                   fields.Datetime.to_string(kiosk.create_date)[:16],
                   ("\nProducts they saw: %s." % products) if products else "",
                   (kiosk.transcript or "")[-6000:])

    def _xb_va_kiosk_conversation(self):
        self.ensure_one()
        key = xb_phone_key(self.whatsapp_number)
        if len(key) < 8:
            return self.env["xb.va.conversation"]
        recent = self.env["xb.va.conversation"].sudo().search([
            ("phone", "!=", False), ("create_date", ">=", fields.Datetime.now() - timedelta(days=KIOSK_DAYS)),
        ], order="id desc", limit=50)
        return recent.filtered(lambda c: xb_phone_key(c.phone) == key)[:1]
