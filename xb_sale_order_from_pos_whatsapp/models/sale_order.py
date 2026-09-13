# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS - WhatsApp add-on
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
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
    xb_wa_amount_unpaid = fields.Char(
        string="Balance due (WhatsApp)", compute="_compute_xb_wa_values"
    )
    xb_wa_kind_label = fields.Char(
        string="Document word (WhatsApp)",
        compute="_compute_xb_wa_values",
        help="\"order\" or \"layaway\" in the customer's language, for \"Your order ... "
             "is ready\".",
    )
    # "Order ready" notice, sent with the company's template (res.company).
    xb_ready_notified_date = fields.Datetime(
        string="Ready notice sent",
        readonly=True,
        copy=False,
        help="When the customer was told by WhatsApp that this order is ready.",
    )
    xb_can_notify_ready = fields.Boolean(
        string="Ready notice available", compute="_compute_xb_can_notify_ready"
    )

    @api.depends(
        "amount_total", "amount_unpaid", "currency_id", "validity_date",
        "partner_id.lang", "xb_so_kind",
    )
    def _compute_xb_wa_values(self):
        for order in self:
            env = order.with_context(lang=order.partner_id.lang or order.env.lang).env
            order.xb_wa_amount_total = format_amount(env, order.amount_total, order.currency_id)
            order.xb_wa_amount_unpaid = format_amount(env, order.amount_unpaid, order.currency_id)
            # WhatsApp rejects an empty variable: an open-ended quotation still gets
            # a readable value.
            order.xb_wa_validity_date = (
                format_date(env, order.validity_date) if order.validity_date else "-"
            )
            if order.xb_so_kind == "layaway":
                order.xb_wa_kind_label = env._("layaway")
            elif order.xb_so_kind == "order_layaway":
                order.xb_wa_kind_label = env._("order / layaway")
            else:
                order.xb_wa_kind_label = env._("order")

    @api.depends("company_id.xb_ready_wa_template_id", "state", "xb_so_kind")
    def _compute_xb_can_notify_ready(self):
        # Orders and layaways (born "sent" at the POS until their first payment) and
        # any confirmed order; never a plain quotation.
        for order in self:
            order.xb_can_notify_ready = bool(
                order.company_id.xb_ready_wa_template_id
                and order.state in ("sent", "sale")
                and (
                    order.state == "sale"
                    or order.xb_so_kind in ("order", "layaway", "order_layaway")
                )
            )

    def _get_whatsapp_safe_fields(self):
        return super()._get_whatsapp_safe_fields() | {
            "xb_wa_amount_total", "xb_wa_validity_date",
            "xb_wa_amount_unpaid", "xb_wa_kind_label",
        }

    def _xb_whatsapp_failure(self, message):
        return message and (
            message.failure_reason
            or dict(message._fields["failure_type"]._description_selection(message.env)).get(
                message.failure_type
            )
        )

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
            raise UserError(self._xb_whatsapp_failure(message) or _("WhatsApp did not accept the message."))
        return message.mobile_number_formatted or phone

    def action_xb_notify_ready(self):
        """Tell the customer by WhatsApp that the order is ready, with the company's
        "order ready" template. A row button of the orders list, which is also the list
        the POS opens to recover an order, so it works in Sales and at the POS alike."""
        user = self.env.user
        if not (
            user.has_group("point_of_sale.group_pos_user")
            or user.has_group("sales_team.group_sale_salesman")
        ):
            raise AccessError(_("Only Sales or Point of Sale users can send this notice."))
        sent_to = []
        # Cashiers may lack Sales rights; what keeps this safe is that it only sends the
        # company's own approved template to the order's own customer.
        for order in self.sudo():
            template = order.company_id.xb_ready_wa_template_id
            if not template:
                raise UserError(_("%s has no WhatsApp template for ready orders.", order.company_id.name))
            if template.status != "approved":
                raise UserError(_("The WhatsApp template %s is not approved by Meta yet.", template.name))
            # Same gate as the buttons: orders / layaways only, never a plain quotation.
            if not order.xb_can_notify_ready:
                raise UserError(_("%s is not an order or layaway waiting to be delivered.", order.name))
            phone = order.partner_id.phone
            if not phone:
                raise UserError(_(
                    "%(customer)s has no phone number: add it to the contact and try again.",
                    customer=order.partner_id.display_name,
                ))
            composer = (
                self.env["whatsapp.composer"]
                .sudo()
                .with_company(order.company_id)
                .with_context(
                    active_model=order._name,
                    active_id=order.id,
                    default_wa_template_id=template.id,
                )
                .create({"phone": phone, "wa_template_id": template.id, "res_model": order._name})
            )
            message = composer._send_whatsapp_template()[:1]
            if not message or message.state == "error":
                raise UserError(self._xb_whatsapp_failure(message) or _("WhatsApp did not accept the message."))
            order.xb_ready_notified_date = fields.Datetime.now()
            sent_to.append(message.mobile_number_formatted or phone)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": _("Ready notice sent by WhatsApp to %s.", ", ".join(sent_to)),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
