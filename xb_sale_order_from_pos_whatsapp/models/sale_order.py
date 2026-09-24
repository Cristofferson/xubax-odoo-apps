# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS - WhatsApp add-on
from datetime import datetime, time

import pytz

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
    # "Order late" notice: new delivery date, sent with the company's template. The
    # date is the order's own delivery date (commitment_date), so everyone sees the
    # promise that was made to the customer.
    xb_wa_delivery_date = fields.Char(
        string="Delivery date (WhatsApp)",
        compute="_compute_xb_wa_delivery_date",
        help="The order's delivery date as the customer reads it, e.g. \"Saturday, "
             "September 26\", in the customer's language.",
    )
    xb_can_notify_delay = fields.Boolean(
        string="Late notice available", compute="_compute_xb_can_notify_delay"
    )
    xb_can_notify_wa = fields.Boolean(
        string="WhatsApp notices available", compute="_compute_xb_can_notify_wa",
        help="At least one WhatsApp notice (ready, late, balance due...) can be sent about "
             "this order.",
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

    def _xb_is_order_to_deliver(self):
        # Orders and layaways (born "sent" at the POS until their first payment) and
        # any confirmed order; never a plain quotation.
        self.ensure_one()
        return self.state in ("sent", "sale") and (
            self.state == "sale" or self.xb_so_kind in ("order", "layaway", "order_layaway")
        )

    @api.depends("company_id.xb_ready_wa_template_id", "state", "xb_so_kind")
    def _compute_xb_can_notify_ready(self):
        for order in self:
            order.xb_can_notify_ready = bool(
                order.company_id.xb_ready_wa_template_id and order._xb_is_order_to_deliver()
            )

    @api.depends("company_id.xb_delay_wa_template_id", "state", "xb_so_kind")
    def _compute_xb_can_notify_delay(self):
        for order in self:
            order.xb_can_notify_delay = bool(
                order.company_id.xb_delay_wa_template_id and order._xb_is_order_to_deliver()
            )

    @api.depends(
        "company_id.xb_ready_wa_template_id", "company_id.xb_delay_wa_template_id",
        "company_id.xb_payment_wa_template_id", "company_id.xb_pickup_wa_template_id",
        "company_id.xb_detail_wa_template_id", "state", "xb_so_kind", "amount_unpaid",
        "xb_ready_notified_date",
    )
    def _compute_xb_can_notify_wa(self):
        for order in self:
            order.xb_can_notify_wa = bool(order._xb_wa_available_notices())

    @api.depends("commitment_date", "partner_id.lang", "partner_id.tz")
    def _compute_xb_wa_delivery_date(self):
        for order in self:
            order.xb_wa_delivery_date = order._xb_wa_format_day(order._xb_delivery_day())

    def _xb_tz(self):
        self.ensure_one()
        return (
            self.partner_id.tz or self.company_id.partner_id.tz or self.env.user.tz
            or "America/Mexico_City"
        )

    def _xb_delivery_day(self):
        """The delivery date as a day in the customer's time zone."""
        self.ensure_one()
        if not self.commitment_date:
            return False
        return fields.Datetime.context_timestamp(
            self.with_context(tz=self._xb_tz()), self.commitment_date
        ).date()

    def _xb_wa_format_day(self, day):
        """A day as the customer reads it: "sábado 26 de septiembre" in Spanish, the
        year only when it is not this year. WhatsApp rejects an empty variable: no date
        gives "-"."""
        self.ensure_one()
        if not day:
            return "-"
        lang = self.partner_id.lang or self.env.lang or "en_US"
        same_year = day.year == fields.Date.context_today(self).year
        if lang.startswith("es"):
            pattern = "EEEE d 'de' MMMM" if same_year else "EEEE d 'de' MMMM 'de' y"
        else:
            pattern = "EEEE, MMMM d" if same_year else "full"
        return format_date(self.env, day, lang_code=lang, date_format=pattern)

    def _get_whatsapp_safe_fields(self):
        return super()._get_whatsapp_safe_fields() | {
            "xb_wa_amount_total", "xb_wa_validity_date",
            "xb_wa_amount_unpaid", "xb_wa_kind_label", "xb_wa_delivery_date",
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

    def _xb_check_notice_rights(self):
        user = self.env.user
        if not (
            user.has_group("point_of_sale.group_pos_user")
            or user.has_group("sales_team.group_sale_salesman")
        ):
            raise AccessError(_("Only Sales or Point of Sale users can send this notice."))

    # The WhatsApp notices the seller can send about an order, in the order the window
    # lists them, each with the company field holding its template. One button opens
    # them all; adding another notice here (and its company field) is all it takes for
    # it to show up in that window.
    XB_WA_NOTICES = {
        "ready": "xb_ready_wa_template_id",
        "pickup": "xb_pickup_wa_template_id",
        "payment": "xb_payment_wa_template_id",
        "detail": "xb_detail_wa_template_id",
        "delay": "xb_delay_wa_template_id",
    }

    def _xb_wa_notice_template(self, notice_type):
        self.ensure_one()
        return self.company_id.sudo()[self.XB_WA_NOTICES[notice_type]]

    def _xb_wa_notice_applies(self, notice_type):
        """Whether the notice makes sense for this order right now, template aside."""
        self.ensure_one()
        if not self._xb_is_order_to_deliver():
            return False
        if notice_type == "pickup":
            # Only a reminder once the customer was told it is ready.
            return bool(self.xb_ready_notified_date)
        if notice_type == "payment":
            return self.currency_id.compare_amounts(self.amount_unpaid, 0) > 0
        return True

    def _xb_wa_available_notices(self):
        """The notices the seller can send about this order: the company has their
        template and they apply to the order."""
        self.ensure_one()
        return [
            code for code in self.XB_WA_NOTICES
            if self._xb_wa_notice_template(code) and self._xb_wa_notice_applies(code)
        ]

    def _xb_wa_managed_templates(self):
        """The templates this add-on sends itself (the notices and the automatic
        messages). They fill variables the plain WhatsApp window knows nothing about
        (the new date of a late order...), so that window must not offer them."""
        self.ensure_one()
        company = self.company_id.sudo()
        templates = self.env["whatsapp.template"]
        for field_name in self.XB_WA_NOTICES.values():
            templates |= company[field_name]
        templates |= self.env["xb.sale.order.wa.automation"].sudo().search(
            [("company_id", "=", company.id)]
        ).template_id
        # The quotation template carries the ticket as its header image: sent from the
        # plain window it would go with the sample image it was approved with.
        templates |= self._xb_wa_quotation_templates()
        return templates

    def _xb_wa_other_templates(self):
        """Approved WhatsApp templates about orders that are not one of ours (e.g. the
        quotation): what "Another message" leads to."""
        self.ensure_one()
        return self.env["whatsapp.template"].search([
            ("model", "=", "sale.order"),
            ("status", "=", "approved"),
            ("id", "not in", self._xb_wa_managed_templates().ids),
            "|", ("allowed_user_ids", "=", False), ("allowed_user_ids", "in", self.env.user.ids),
        ])

    def _xb_wa_composer_action(self):
        """The standard WhatsApp window, without the templates this add-on manages.

        The composer is created here, bound to this order, and the window opens on it.
        Opening it from a context instead does not work from the notices window: the web
        client puts that window's own id in active_ids, and the composer takes active_ids
        for the order (another order, possibly of another company)."""
        self.ensure_one()
        hidden = self._xb_wa_managed_templates()
        others = self._xb_wa_other_templates()
        context = {
            "active_model": self._name,
            "active_id": self.id,
            "active_ids": [self.id],
            "xb_hide_template_ids": hidden.ids,
        }
        values = {"res_model": self._name, "res_ids": str([self.id])}
        if others:
            values["wa_template_id"] = others[:1].id
        composer = self.env["whatsapp.composer"].with_context(context).create(values)
        return {
            "type": "ir.actions.act_window",
            "name": _("Send WhatsApp Message"),
            "res_model": "whatsapp.composer",
            "res_id": composer.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": context,
        }

    def action_xb_whatsapp_from_chatter(self):
        """The WhatsApp button of the order's chatter. One button per order, not two:
        it opens the notices window (which also sends the quotation) when it has
        something to offer, and the standard WhatsApp window otherwise."""
        self.ensure_one()
        if self.env["xb.sale.order.whatsapp.notice"]._xb_types_for(self):
            try:
                return self.action_xb_notify_whatsapp()
            except AccessError:
                pass
        if not self._xb_wa_other_templates():
            raise UserError(_("There is no WhatsApp message to send about %s right now.", self.name))
        return self._xb_wa_composer_action()

    def _xb_send_wa_notice(self, notice_type, phone=None, new_date=None):
        """Send one of the WhatsApp notices about this order and return the number it
        went to. Runs sudo: cashiers may lack Sales rights, and what keeps it safe is
        that it only sends the company's own approved template to the order's own
        customer."""
        self.ensure_one()
        self._xb_check_notice_rights()
        order = self.sudo()
        template = order._xb_wa_notice_template(notice_type)
        if not template:
            raise UserError(_("%s has no WhatsApp template for this notice.", order.company_id.name))
        if template.status != "approved":
            raise UserError(_("The WhatsApp template %s is not approved by Meta yet.", template.name))
        # Same gate as the button: orders / layaways only, never a plain quotation.
        if not order._xb_is_order_to_deliver():
            raise UserError(_("%s is not an order or layaway waiting to be delivered.", order.name))
        if notice_type == "payment" and not order._xb_wa_notice_applies("payment"):
            raise UserError(_("%s has no balance due.", order.name))
        if notice_type == "pickup" and not order._xb_wa_notice_applies("pickup"):
            raise UserError(_(
                "The customer has not been told that %s is ready: send that notice first.",
                order.name,
            ))
        phone = phone or order.partner_id.phone
        if not phone:
            raise UserError(_(
                "%(customer)s has no phone number: add it to the contact and try again.",
                customer=order.partner_id.display_name,
            ))
        if notice_type == "delay":
            if not new_date:
                raise UserError(_("Pick the new delivery date."))
            if new_date < fields.Date.context_today(self):
                raise UserError(_("The new delivery date cannot be before today."))
            # Midday in the seller's time zone: the day stays the same in any Mexican
            # (or US) time zone the customer may be in. The date the message prints is
            # the order's, so it is set before sending; if WhatsApp refuses the
            # message, the error rolls the date back too.
            tz = pytz.timezone(self.env.user.tz or order._xb_tz())
            noon = tz.localize(datetime.combine(new_date, time(12, 0)))
            order.commitment_date = noon.astimezone(pytz.utc).replace(tzinfo=None)
        # Same rule as the quotation: fill the customer's phone only when it has none;
        # a different number is used for this send only.
        if not order.partner_id.phone:
            order.partner_id.phone = phone
        message = order._xb_wa_send_template(template, phone=phone)
        # Logged: the automatic reminders keep quiet after a notice sent by hand.
        order._xb_wa_log("notice_" + notice_type, message=message)
        if notice_type == "ready":
            order.xb_ready_notified_date = fields.Datetime.now()
        elif notice_type == "delay":
            # A late order is no longer "ready": the ready notice can be sent again when
            # it really is.
            order.xb_ready_notified_date = False
        return message.mobile_number_formatted or phone

    def action_xb_notify_ready(self):
        """Tell the customer the order is ready, asking nothing. Kept for automations
        and for other modules (the jewelry workshop bridge calls it)."""
        sent_to = [order._xb_send_wa_notice("ready") for order in self]
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": _("Ready notice sent by WhatsApp to %s.", ", ".join(sent_to)),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def action_xb_notify_whatsapp(self):
        """One button for every WhatsApp notice about the order: it opens a window
        where the seller picks what to tell the customer, reads the exact message and
        sends it. A row button of the orders list, which is also the list the POS opens
        to recover an order, so it works in Sales and at the POS alike."""
        self.ensure_one()
        self._xb_check_notice_rights()
        return {
            "type": "ir.actions.act_window",
            "name": _("Notify the customer by WhatsApp"),
            "res_model": "xb.sale.order.whatsapp.notice",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {"default_order_id": self.id},
        }
