# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS - WhatsApp add-on
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_amount, format_date


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Ready-to-read values for WhatsApp template variables. WhatsApp prints a raw
    # field with str(): amount_total would read "12500.0" and validity_date
    # "2026-10-12". These give what the customer reads on the ticket, in the
    # customer's language. Not stored: no column, nothing to migrate.
    xb_wa_amount_total = fields.Char(
        string="Total (WhatsApp)", compute="_compute_xb_wa_values"
    )
    xb_wa_validity_date = fields.Char(
        string="Expiration (WhatsApp)", compute="_compute_xb_wa_values"
    )

    @api.depends("amount_total", "currency_id", "validity_date", "partner_id.lang")
    def _compute_xb_wa_values(self):
        for order in self:
            env = order.with_context(lang=order.partner_id.lang or order.env.lang).env
            order.xb_wa_amount_total = format_amount(env, order.amount_total, order.currency_id)
            # WhatsApp rejects an empty variable: an open-ended quotation still gets
            # a readable value.
            order.xb_wa_validity_date = (
                format_date(env, order.validity_date) if order.validity_date else "-"
            )

    def _get_whatsapp_safe_fields(self):
        return super()._get_whatsapp_safe_fields() | {"xb_wa_amount_total", "xb_wa_validity_date"}

    def _xb_pos_send_whatsapp(self, phone, config, ticket):
        template = config.xb_quotation_wa_template_id
        if not template:
            raise UserError(_("This Point of Sale has no WhatsApp template for quotations."))
        if template.status != "approved":
            raise UserError(_("The WhatsApp template %s is not approved by Meta yet.", template.name))
        partner = self.partner_id
        # Same rule as the email: fill the customer's phone only when it has none; a
        # different number is used for this send only.
        if not partner.phone:
            partner.phone = phone
        # The ticket goes in the template's image header, exactly like the native
        # WhatsApp POS receipt (whatsapp_pos): the customer gets the printed ticket.
        composer = (
            self.env["whatsapp.composer"]
            .with_company(self.company_id)
            .with_context(
                active_model=self._name,
                active_id=self.id,
                default_wa_template_id=template.id,
            )
            .create({
                "phone": phone,
                "wa_template_id": template.id,
                "res_model": self._name,
                "attachment_id": ticket.id,
            })
        )
        message = composer._send_whatsapp_template()[:1]
        if not message or message.state == "error":
            failure = message and (
                message.failure_reason
                or dict(message._fields["failure_type"]._description_selection(message.env)).get(
                    message.failure_type
                )
            )
            raise UserError(failure or _("WhatsApp did not accept the message."))
        return message.mobile_number_formatted or phone
