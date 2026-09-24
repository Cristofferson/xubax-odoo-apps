# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS - WhatsApp add-on
from odoo import api, fields, models


class XbSaleOrderWhatsappNotice(models.TransientModel):
    """One window for every WhatsApp notice about an order: the seller picks what to
    tell the customer ("it is ready", "a balance is due", "it is late, here is the new
    date"...), reads the exact message and sends it. One button in the orders list
    instead of one per notice."""

    _name = "xb.sale.order.whatsapp.notice"
    _description = "Notify the customer by WhatsApp"

    order_id = fields.Many2one("sale.order", string="Order", required=True, readonly=True)
    # Only the notices that apply to this order and whose template its company has.
    available_type_ids = fields.Many2many(
        "xb.sale.order.whatsapp.notice.type", compute="_compute_available_type_ids"
    )
    notice_type_id = fields.Many2one(
        "xb.sale.order.whatsapp.notice.type",
        string="What do we tell the customer?",
        required=True,
        domain="[('id', 'in', available_type_ids)]",
    )
    notice_type = fields.Char(related="notice_type_id.code")
    partner_id = fields.Many2one(related="order_id.partner_id")
    ready_notified_date = fields.Datetime(related="order_id.xb_ready_notified_date")
    current_date = fields.Datetime(
        related="order_id.commitment_date", string="Current delivery date"
    )
    new_date = fields.Date(string="New delivery date")
    # Required in the view only: a stored compute is written after the row is created.
    phone = fields.Char(
        string="Mobile",
        compute="_compute_phone",
        store=True,
        readonly=False,
        help="A number typed for a customer who had none is saved on the contact; an "
             "existing one is only replaced for this message.",
    )
    # Not sanitized: drawn here from the template and the order (values escaped by
    # QWeb), and it carries the quotation image as a data URI.
    preview_whatsapp = fields.Html(
        compute="_compute_preview_whatsapp", string="Message preview", sanitize=False
    )
    quotation_image = fields.Binary(
        string="Quotation image", compute="_compute_quotation_image",
        help="The image of the quotation that goes at the top of the message.",
    )

    @api.model
    def _xb_types_for(self, order):
        codes = order.sudo()._xb_wa_available_notices() if order else []
        # A quotation can be sent from here too, with an image of it as the ticket.
        if order and order.sudo()._xb_wa_quotation_applies():
            codes = ["quotation"] + codes
        types = self.env["xb.sale.order.whatsapp.notice.type"].search([("code", "in", codes)])
        return types.sorted(lambda t: codes.index(t.code))

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if "notice_type_id" in fields_list and not values.get("notice_type_id"):
            order = self.env["sale.order"].browse(self.env.context.get("default_order_id"))
            types = self._xb_types_for(order)
            # Already told it is ready: the likely next step is the pick-up reminder.
            pickup = types.filtered(lambda t: t.code == "pickup")
            if pickup and order.xb_ready_notified_date:
                values["notice_type_id"] = pickup.id
            elif types:
                values["notice_type_id"] = types[0].id
        return values

    @api.depends("order_id")
    def _compute_available_type_ids(self):
        for wizard in self:
            wizard.available_type_ids = self._xb_types_for(wizard.order_id)

    @api.depends("order_id")
    def _compute_phone(self):
        for wizard in self:
            wizard.phone = wizard.order_id.partner_id.phone

    @api.depends("order_id", "notice_type_id", "new_date", "quotation_image")
    def _compute_preview_whatsapp(self):
        for wizard in self:
            order = wizard.order_id
            if wizard.notice_type == "quotation":
                template = order.sudo()._xb_wa_quotation_template()
            elif wizard.notice_type:
                template = order._xb_wa_notice_template(wizard.notice_type)
            else:
                template = None
            if not template:
                wizard.preview_whatsapp = False
                continue
            preview = str(self.env["ir.qweb"]._render("whatsapp.template_message_preview", {
                "body": template._get_formatted_body(variable_values=wizard._xb_variable_values(template)),
                "buttons": template.button_ids,
                "header_type": template.header_type,
                "footer_text": template.footer_text,
                "language_direction": "ltr",
            }))
            if wizard.notice_type == "quotation" and wizard.quotation_image:
                # The native preview only draws a grey placeholder for an image header:
                # put the real ticket there, so the seller sees exactly what goes out.
                preview = preview.replace(
                    'src="/whatsapp/static/img/image.png"',
                    'src="data:image/jpeg;base64,%s" style="max-height:420px"'
                    % wizard.quotation_image.decode(),
                ).replace("d-block bg-400 p-4 text-center", "d-block text-center").replace(
                    'class="m-2 img-fluid"', 'class="img-fluid rounded-2"'
                )
            wizard.preview_whatsapp = preview

    @api.depends("order_id", "notice_type")
    def _compute_quotation_image(self):
        for wizard in self:
            wizard.quotation_image = (
                wizard.order_id.sudo()._xb_quotation_image(as_base64=True)
                if wizard.notice_type == "quotation" else False
            )

    def _xb_variable_values(self, template):
        # Template values read from the order, with the NEW date in place of the one the
        # order still has: the seller sees what the customer will read.
        self.ensure_one()
        order = self.order_id
        values = template.variable_ids._get_variables_value(order)
        if self.notice_type != "delay":
            return values
        new_day = order._xb_wa_format_day(self.new_date) if self.new_date else "…"
        for variable in template.variable_ids.filtered(
            lambda v: v.field_type == "field" and v.field_name == "xb_wa_delivery_date"
        ):
            values[f"{variable.line_type}-{variable.name}"] = new_day
        return values

    def action_send(self):
        self.ensure_one()
        if self.notice_type == "quotation":
            sent_to = self.order_id._xb_send_wa_quotation(phone=self.phone)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "success",
                    "message": self.env._("Quotation sent by WhatsApp to %s.", sent_to),
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }
        sent_to = self.order_id._xb_send_wa_notice(
            self.notice_type, phone=self.phone, new_date=self.new_date
        )
        if self.notice_type == "delay":
            message = self.env._(
                "Late notice sent by WhatsApp to %(phone)s. New delivery date: %(date)s.",
                phone=sent_to, date=self.order_id._xb_wa_format_day(self.new_date),
            )
        elif self.notice_type == "ready":
            message = self.env._("Ready notice sent by WhatsApp to %s.", sent_to)
        else:
            message = self.env._("Notice sent by WhatsApp to %s.", sent_to)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": message,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
