# -*- coding: utf-8 -*-
from markupsafe import Markup, escape

from odoo import _, api, models
from odoo.exceptions import UserError


class XbVaConversation(models.Model):
    _inherit = "xb.va.conversation"

    @api.model
    def _xb_va_share_channels(self, config):
        channels = super()._xb_va_share_channels(config)
        template = config.sudo().xb_va_wa_send_template_id
        if template and template.status == "approved":
            channels.append("whatsapp")
        return channels

    def _xb_va_share(self, channel, phone):
        if channel != "whatsapp":
            return super()._xb_va_share(channel, phone)
        self.ensure_one()
        conv = self.sudo()
        config = conv.config_id
        template = config.xb_va_wa_send_template_id
        partner = conv._xb_va_find_partner(phone)
        # International format with the shop's country (+52...), as WhatsApp needs it.
        number = partner.phone_sanitized or partner._phone_format(
            number=phone, country=config.company_id.country_id) or phone
        conv.write({"partner_id": partner.id, "phone": number})
        conv._xb_va_ensure_share()
        composer = (
            self.env["whatsapp.composer"].sudo().with_company(config.company_id)
            .with_context(active_model=conv._name, active_id=conv.id, default_wa_template_id=template.id)
            .create({"phone": number, "wa_template_id": template.id, "res_model": conv._name})
        )
        message = composer._send_whatsapp_template()[:1]
        if not message or message.state == "error":
            raise UserError(_("WhatsApp did not accept the message."))
        conv.shared = True
        conv._xb_va_note_partner()
        if config.xb_va_create_lead and "crm.lead" in self.env:
            conv._xb_va_create_lead()
        return message

    def _xb_va_summary_html(self):
        self.ensure_one()
        rows = [Markup("<li>%s — %s</li>") % (t.name, self._xb_va_price_label(t)) for t in self.product_ids]
        lines = [Markup("<p><b>%s:</b> %s</p>") % (
            self.config_id.xb_va_name if who == "seller" else _("Customer"), text)
            for who, text in self._xb_va_transcript_lines()]
        return Markup("<p>%s <a href='%s'>%s</a></p>%s%s") % (
            _("Conversation with the virtual seller at the kiosk %s.", self.config_id.name),
            self.share_url, _("Selection page"),
            Markup("<ul>%s</ul>") % Markup("").join(rows) if rows else "",
            Markup("").join(lines))

    def _xb_va_note_partner(self):
        self.partner_id.message_post(body=self._xb_va_summary_html(), message_type="comment",
                                     subtype_xmlid="mail.mt_note")

    def _xb_va_create_lead(self):
        self.ensure_one()
        config = self.config_id
        products = ", ".join(self.product_ids.mapped("name")[:3])
        return self.env["crm.lead"].sudo().with_company(config.company_id).create({
            "name": _("Kiosk: %s", products or self.partner_id.display_name),
            "type": "opportunity",
            "partner_id": self.partner_id.id,
            "phone": self.phone,
            "company_id": config.company_id.id,
            "user_id": config.xb_va_ho_user_ids[:1].id or False,
            "description": self._xb_va_summary_html(),
        })
