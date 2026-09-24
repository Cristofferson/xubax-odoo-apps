# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS - WhatsApp add-on
"""Automatic WhatsApp messages along an order's life: confirmed, payment received,
waiting to be picked up, delivered, and a follow-up a few days after delivery.

A cron looks at orders / layaways every few minutes and sends what their stage calls
for, instead of hooking every button that moves an order: payments come from the POS,
the backend or a payment link, and all of them end up in the same place. What was sent
is logged (xb.sale.order.wa.log), which makes every message go out once, and nothing
older than the moment an automation was switched on is ever sent.
"""
import logging
from datetime import timedelta

import pytz

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError
from odoo.modules import module as odoo_module

_logger = logging.getLogger(__name__)

# Automatic messages go out between these hours (company's time zone): nobody gets a
# message about their order at 11 pm. A message due at night waits for the morning.
XB_WA_SEND_FROM_HOUR = 9
XB_WA_SEND_UNTIL_HOUR = 21

XB_WA_AUTO_KINDS = [
    ("confirm", "Order / layaway confirmed"),
    ("payment", "Payment received"),
    ("pickup", "Reminder: waiting to be picked up"),
    ("delivered", "Delivered"),
    ("followup", "Follow-up after delivery"),
]
# Reminders (pick-up, follow-up) keep quiet if the customer got something from us in
# the last few days; the rest answer something the customer just did, and go right away.
XB_WA_DEFAULT_DELAY = {"pickup": 7, "followup": 5}


class XbSaleOrderWaAutomation(models.Model):
    """One automatic WhatsApp message of one company: on or off, with its template."""

    _name = "xb.sale.order.wa.automation"
    _description = "Automatic WhatsApp message about orders"
    _order = "company_id, sequence, id"

    company_id = fields.Many2one(
        "res.company", required=True, readonly=True, default=lambda self: self.env.company
    )
    kind = fields.Selection(XB_WA_AUTO_KINDS, required=True, readonly=True)
    sequence = fields.Integer(default=10)
    enabled = fields.Boolean(
        string="On",
        help="Only what happens from the moment it is switched on is sent: switching it "
             "on never writes to customers about older orders.",
    )
    since = fields.Datetime(
        string="On since", readonly=True,
        help="Events before this moment are ignored.",
    )
    template_id = fields.Many2one(
        "whatsapp.template",
        string="Template",
        domain="[('model', '=', 'sale.order'), ('status', '=', 'approved')]",
    )
    delay_days = fields.Integer(
        string="After (days)",
        help="Pick-up reminder: days after the ready notice. Follow-up: days after "
             "delivery.",
    )
    quiet_days = fields.Integer(
        string="Quiet days",
        default=3,
        help="Reminders only: not sent if the customer got any WhatsApp message about "
             "an order in these last days.",
    )
    review_url = fields.Char(
        string="Review link",
        help="Follow-up only: the link to leave a review (e.g. Google). It is sent to "
             "everyone who answers the follow-up; to an unhappy customer, the seller "
             "sends it once the problem is sorted out.",
    )

    _kind_unique = models.Constraint(
        "UNIQUE(company_id, kind)", "Each automatic message exists once per company."
    )

    def write(self, vals):
        # Switched on (again): only what happens from now on counts.
        if vals.get("enabled"):
            for automation in self.filtered(lambda a: not a.enabled):
                super(XbSaleOrderWaAutomation, automation).write(
                    {"since": fields.Datetime.now()}
                )
        return super().write(vals)

    @api.model
    def _xb_ensure(self, company):
        existing = self.sudo().search([("company_id", "=", company.id)]).mapped("kind")
        self.sudo().create([
            {
                "company_id": company.id,
                "kind": kind,
                "sequence": (index + 1) * 10,
                "delay_days": XB_WA_DEFAULT_DELAY.get(kind, 0),
            }
            for index, (kind, _label) in enumerate(XB_WA_AUTO_KINDS)
            if kind not in existing
        ])

    @api.model
    def action_xb_open(self):
        self._xb_ensure(self.env.company)
        return {
            "type": "ir.actions.act_window",
            "name": _("Automatic WhatsApp messages"),
            "res_model": self._name,
            "view_mode": "list",
            "domain": [("company_id", "=", self.env.company.id)],
            "target": "current",
        }

    def _xb_in_send_hours(self):
        self.ensure_one()
        tz = pytz.timezone(self.company_id.partner_id.tz or self.env.user.tz or "America/Mexico_City")
        hour = fields.Datetime.now().replace(tzinfo=pytz.utc).astimezone(tz).hour
        return XB_WA_SEND_FROM_HOUR <= hour < XB_WA_SEND_UNTIL_HOUR


class XbSaleOrderWaLog(models.Model):
    """Every WhatsApp message sent about an order, automatic or by hand: what makes
    each automatic message go out once, and the quiet days of the reminders."""

    _name = "xb.sale.order.wa.log"
    _description = "WhatsApp message sent about an order"
    _order = "date desc, id desc"

    order_id = fields.Many2one("sale.order", required=True, index=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner", index=True, ondelete="cascade")
    company_id = fields.Many2one(related="order_id.company_id", store=True)
    kind = fields.Selection(
        XB_WA_AUTO_KINDS + [
            ("notice_ready", "Notice: ready"),
            ("notice_pickup", "Notice: waiting to be picked up"),
            ("notice_payment", "Notice: balance due"),
            ("notice_detail", "Notice: confirm a detail"),
            ("notice_delay", "Notice: delay"),
        ],
        required=True,
    )
    automatic = fields.Boolean()
    date = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    wa_message_id = fields.Many2one("whatsapp.message", string="WhatsApp message")
    failed = fields.Boolean(help="WhatsApp refused it. Not tried again.")
    failure = fields.Char()
    # Payments this message told the customer about: each POS ticket / online payment
    # is announced once.
    pos_order_ids = fields.Many2many("pos.order", string="POS tickets")
    transaction_ids = fields.Many2many("payment.transaction", string="Online payments")
    reply = fields.Selection(
        [("loved", "Loved it"), ("comment", "Has a comment"), ("unhappy", "Unhappy")],
        help="Follow-up only: the button the customer tapped.",
    )


class SaleOrder(models.Model):
    _inherit = "sale.order"

    xb_wa_log_ids = fields.One2many("xb.sale.order.wa.log", "order_id", string="WhatsApp messages")
    xb_wa_balance_text = fields.Char(
        string="Balance (WhatsApp)",
        compute="_compute_xb_wa_balance_text",
        help="\"Balance due: $650.00.\" or \"It is fully paid.\", in the customer's "
             "language.",
    )

    @api.depends("amount_unpaid", "currency_id", "partner_id.lang")
    def _compute_xb_wa_balance_text(self):
        for order in self:
            env = order.with_context(lang=order.partner_id.lang or order.env.lang).env
            if order.currency_id.is_zero(order.amount_unpaid):
                order.xb_wa_balance_text = env._("It is fully paid.")
            else:
                order.xb_wa_balance_text = env._(
                    "Balance due: %s.", tools.format_amount(env, order.amount_unpaid, order.currency_id)
                )

    def _get_whatsapp_safe_fields(self):
        return super()._get_whatsapp_safe_fields() | {"xb_wa_balance_text"}

    # --- What happened to the order -------------------------------------------------
    def _xb_wa_payment_events(self):
        """POS tickets and online payments that paid something on this order."""
        self.ensure_one()
        tickets = self.sudo().order_line.pos_order_line_ids.order_id.filtered(
            lambda t: t.state in ("paid", "done", "invoiced")
            and sum(
                line.price_subtotal_incl for line in t.lines
                if line.sale_order_origin_id == self
            ) > 0
        )
        online = self.sudo().transaction_ids.filtered(
            lambda tx: tx.state == "done" and tx.amount > 0
        )
        return tickets, online

    def _xb_wa_has_goods(self):
        self.ensure_one()
        return any(
            not line.display_type and not line.is_downpayment and line.product_id.type == "consu"
            for line in self.order_line
        )

    def _xb_wa_delivered_at(self):
        """When the goods were handed over: the last done delivery or the POS ticket
        that settled them. False while something is still to be delivered."""
        self.ensure_one()
        if not self._xb_wa_has_goods() or self.xb_pending_delivery:
            return False
        # picking_ids comes with sale_stock, which this module does not require.
        pickings = self.sudo().picking_ids if "picking_ids" in self._fields else []
        dates = [
            picking.date_done for picking in pickings
            if picking.state == "done" and picking.picking_type_code == "outgoing"
        ]
        dates += [
            line.order_id.date_order
            for line in self.sudo().order_line.pos_order_line_ids
            if line.qty > 0 and line.product_id.type == "consu"
            and line.order_id.state in ("paid", "done", "invoiced")
        ]
        return max(dates) if dates else False

    def _xb_wa_logged(self, *kinds, since=False, sent_only=True):
        self.ensure_one()
        return self.xb_wa_log_ids.filtered(
            lambda log: log.kind in kinds
            and (not since or log.date >= since)
            and (not sent_only or not log.failed)
        )

    # --- Sending -----------------------------------------------------------------------
    def _xb_wa_send_template(self, template, phone=None, attachment=None):
        """Send an approved template about this order and return the whatsapp.message.
        ``attachment`` is the header image/document, when the template has one.
        Raises UserError when WhatsApp refuses it."""
        self.ensure_one()
        order = self.sudo()
        phone = phone or order.partner_id.phone
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
            .create({
                "phone": phone,
                "wa_template_id": template.id,
                "res_model": order._name,
                "attachment_id": attachment.id if attachment else False,
            })
        )
        message = composer._send_whatsapp_template()[:1]
        if not message or message.state == "error":
            raise UserError(self._xb_whatsapp_failure(message) or _("WhatsApp did not accept the message."))
        return message

    def _xb_wa_blacklisted(self):
        self.ensure_one()
        number = self.partner_id.phone and self.partner_id._phone_format(number=self.partner_id.phone)
        return bool(number) and bool(
            self.env["phone.blacklist"].sudo().search_count([("number", "=", number)])
        )

    def _xb_wa_log(self, kind, message=None, automatic=False, failure=None, tickets=None, online=None):
        self.ensure_one()
        return self.env["xb.sale.order.wa.log"].sudo().create({
            "order_id": self.id,
            "partner_id": self.partner_id.id,
            "kind": kind,
            "automatic": automatic,
            "wa_message_id": message.id if message else False,
            "failed": bool(failure),
            "failure": failure and str(failure)[:250],
            "pos_order_ids": [(6, 0, tickets.ids)] if tickets else False,
            "transaction_ids": [(6, 0, online.ids)] if online else False,
        })

    # --- The cron ----------------------------------------------------------------------
    @api.model
    def _cron_xb_wa_journey(self):
        automations = self.env["xb.sale.order.wa.automation"].sudo().search([
            ("enabled", "=", True), ("since", "!=", False),
            ("template_id.status", "=", "approved"),
        ])
        for company in automations.company_id:
            by_kind = {a.kind: a for a in automations if a.company_id == company}
            if not next(iter(by_kind.values()))._xb_in_send_hours():
                continue
            orders = self.sudo().with_company(company).search([
                ("company_id", "=", company.id),
                ("xb_so_kind", "in", ("order", "layaway", "order_layaway")),
                ("state", "in", ("sent", "sale")),
                ("create_date", ">=", min(by_kind.values(), key=lambda a: a.since).since - timedelta(days=365)),
            ])
            for order in orders:
                try:
                    with self.env.cr.savepoint():
                        order._xb_wa_journey_step(by_kind)
                except Exception:  # noqa: BLE001 - one order never stops the others
                    _logger.exception("xb WhatsApp journey: order %s failed", order.name)
                # A message that left must never be sent again because a later order
                # rolled the transaction back.
                if not odoo_module.current_test and self.env.context.get("xb_wa_commit", True):
                    self.env.cr.commit()

    def _xb_wa_journey_step(self, by_kind):
        """Send the one automatic message this order is due, if any: at most one per
        order and per run, the most urgent first."""
        self.ensure_one()
        if not self.partner_id.phone or self._xb_wa_blacklisted():
            return False
        now = fields.Datetime.now()
        tickets, online = self._xb_wa_payment_events()
        told = self._xb_wa_logged("confirm", "payment", "delivered", sent_only=False)
        new_tickets = tickets - told.pos_order_ids
        new_online = online - told.transaction_ids

        def due(kind):
            automation = by_kind.get(kind)
            return automation if automation and automation.template_id else False

        # 1. Delivered: the goods were handed over after switching on. First, because
        #    an order paid and handed over on the same ticket only gets this one.
        auto = due("delivered")
        delivered_at = self._xb_wa_delivered_at()
        if (
            auto and delivered_at and delivered_at >= auto.since
            and not self._xb_wa_logged("delivered", sent_only=False)
        ):
            return self._xb_wa_auto_send(auto, tickets=new_tickets, online=new_online)

        # 2. Confirmed: the first payment of an order / layaway made after switching on,
        #    while the piece is still to be handed over.
        auto = due("confirm")
        if (
            auto and not delivered_at and self.state == "sale" and (tickets or online)
            and not self._xb_wa_logged("confirm", "delivered", sent_only=False)
            and self.date_order and self.date_order >= auto.since
        ):
            return self._xb_wa_auto_send(auto, tickets=new_tickets, online=new_online)

        # 3. Payment received: tickets / online payments nobody was told about. Several
        #    since the last run go in one message: it says the balance as it is now.
        auto = due("payment")
        if auto and not delivered_at:
            fresh_tickets = new_tickets.filtered(lambda t: t.date_order >= auto.since)
            fresh_online = new_online.filtered(
                lambda tx: (tx.last_state_change or tx.create_date) >= auto.since
            )
            if fresh_tickets or fresh_online:
                return self._xb_wa_auto_send(auto, tickets=fresh_tickets, online=fresh_online)

        # 4. Waiting to be picked up: told it is ready some days ago, still not here.
        auto = due("pickup")
        ready = self.xb_ready_notified_date
        if (
            auto and ready and ready >= auto.since and self.xb_pending_delivery
            and ready + timedelta(days=auto.delay_days) <= now
            and not self._xb_wa_logged("pickup", "notice_pickup", since=ready, sent_only=False)
            and not self._xb_wa_recent_contact(auto.quiet_days)
        ):
            return self._xb_wa_auto_send(auto)

        # 5. Follow-up: some days after delivery, once.
        auto = due("followup")
        if (
            auto and delivered_at and delivered_at >= auto.since
            and delivered_at + timedelta(days=auto.delay_days) <= now
            and not self._xb_wa_logged("followup", sent_only=False)
            and not self._xb_wa_recent_contact(auto.quiet_days)
        ):
            return self._xb_wa_auto_send(auto)
        return False

    def _xb_wa_recent_contact(self, days):
        self.ensure_one()
        if not days:
            return False
        return bool(self.env["xb.sale.order.wa.log"].sudo().search_count([
            ("partner_id", "=", self.partner_id.id),
            ("failed", "=", False),
            ("date", ">=", fields.Datetime.now() - timedelta(days=days)),
        ]))

    def _xb_wa_auto_send(self, automation, tickets=None, online=None):
        self.ensure_one()
        try:
            message = self._xb_wa_send_template(automation.template_id)
        except UserError as error:
            # Logged as failed so it is not tried at every run; the seller sees why.
            self._xb_wa_log(automation.kind, automatic=True, failure=error.args[0],
                            tickets=tickets, online=online)
            self.sudo().message_post(body=_(
                "The automatic WhatsApp message \"%(kind)s\" could not be sent: %(error)s",
                kind=dict(automation._fields["kind"]._description_selection(self.env))[automation.kind],
                error=error.args[0],
            ))
            return False
        self._xb_wa_log(automation.kind, message=message, automatic=True,
                        tickets=tickets, online=online)
        return message
