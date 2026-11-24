# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS
# Layaway terms (1.3.0): a deadline, a minimum down payment, a minimum payment, a
# cancellation fee, reminders, the expiry of an unpaid layaway and the goods it holds.
# Original, clean-room implementation over native Odoo (sale, pos_sale, stock).
import logging
from datetime import datetime, timedelta

import pytz

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round
from odoo.tools.misc import format_date, formatLang

_logger = logging.getLogger(__name__)

LAYAWAY_KINDS = ("layaway",)
ORDER_KINDS = ("order", "order_layaway")


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Terms, copied from the company when the layaway is made (the customer keeps the
    # terms they accepted even if the shop changes its settings later).
    xb_layaway_deadline = fields.Date(
        string="Layaway deadline", copy=False, tracking=True,
        help="Last day to pay the layaway in full. The day after, an unpaid layaway "
        "expires.",
    )
    xb_layaway_down_percent = fields.Float(string="Minimum down payment (%)", copy=False)
    xb_layaway_min_payment = fields.Monetary(string="Minimum payment", copy=False)
    xb_layaway_cancel_fee_percent = fields.Float(string="Cancellation fee (%)", copy=False)
    xb_layaway_expired_on = fields.Date(string="Expired on", copy=False, readonly=True)
    xb_layaway_activity_id = fields.Many2one(
        "mail.activity", string="Expiry to-do", copy=False, readonly=True, ondelete="set null")
    xb_layaway_state = fields.Selection(
        selection=[
            ("draft", "Without down payment"),
            ("active", "Active"),
            ("paid", "Paid in full"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        string="Layaway status", compute="_compute_xb_layaway_state", store=True, index=True,
    )
    xb_layaway_paid = fields.Monetary(
        string="Paid so far", compute="_compute_xb_layaway_amounts",
        help="What the customer has paid towards this layaway.",
    )
    xb_layaway_progress = fields.Float(string="Paid (%)", compute="_compute_xb_layaway_amounts")
    xb_layaway_fee_amount = fields.Monetary(
        string="Cancellation fee", compute="_compute_xb_layaway_amounts",
        help="What the shop keeps of the payments if the layaway expires unpaid.",
    )
    xb_layaway_refund_amount = fields.Monetary(
        string="To return to the customer", compute="_compute_xb_layaway_amounts",
    )
    xb_layaway_days_left = fields.Integer(string="Days left", compute="_compute_xb_layaway_days_left")

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("xb_so_kind", "state", "amount_unpaid", "amount_total", "xb_layaway_expired_on")
    def _compute_xb_layaway_state(self):
        for order in self:
            if order.xb_so_kind not in LAYAWAY_KINDS:
                order.xb_layaway_state = False
            elif order.state == "cancel":
                order.xb_layaway_state = "cancelled"
            elif order.currency_id.compare_amounts(order.amount_unpaid, 0.0) <= 0:
                order.xb_layaway_state = "paid"
            elif order.xb_layaway_expired_on:
                order.xb_layaway_state = "expired"
            elif order.state in ("draft", "sent"):
                order.xb_layaway_state = "draft"
            else:
                order.xb_layaway_state = "active"

    @api.depends("amount_total", "amount_unpaid", "xb_layaway_cancel_fee_percent")
    def _compute_xb_layaway_amounts(self):
        for order in self:
            if order.xb_so_kind not in LAYAWAY_KINDS + ORDER_KINDS:
                order.xb_layaway_paid = order.xb_layaway_progress = 0.0
                order.xb_layaway_fee_amount = order.xb_layaway_refund_amount = 0.0
                continue
            paid = order.currency_id.round(max(order.amount_total - order.amount_unpaid, 0.0))
            fee = (order.currency_id.round(paid * (order.xb_layaway_cancel_fee_percent or 0.0) / 100.0)
                   if order.xb_so_kind in LAYAWAY_KINDS else 0.0)
            order.xb_layaway_paid = paid
            order.xb_layaway_progress = (
                min(paid / order.amount_total * 100.0, 100.0) if order.amount_total else 0.0
            )
            order.xb_layaway_fee_amount = fee
            order.xb_layaway_refund_amount = paid - fee

    @api.depends("xb_layaway_deadline")
    def _compute_xb_layaway_days_left(self):
        for order in self:
            order.xb_layaway_days_left = (
                (order.xb_layaway_deadline - order._xb_layaway_today()).days
                if order.xb_layaway_deadline else 0
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _xb_layaway_tz(self):
        company = self[:1].company_id or self.env.company
        return pytz.timezone(
            company.partner_id.tz or self.env.user.tz or "America/Mexico_City"
        )

    def _xb_layaway_today(self):
        """Today in the shop's time zone: a layaway's last day ends at the shop's
        midnight, whoever (or whatever cron) is asking."""
        return datetime.now(pytz.utc).astimezone(self[:1]._xb_layaway_tz()).date()

    @api.model
    def _xb_layaway_terms(self, company):
        """The terms a new layaway takes from its company."""
        today = datetime.now(pytz.utc).astimezone(
            pytz.timezone(company.partner_id.tz or self.env.user.tz or "America/Mexico_City")
        ).date()
        return {
            "xb_layaway_deadline": (
                today + timedelta(days=company.xb_layaway_days) if company.xb_layaway_days > 0 else False
            ),
            "xb_layaway_down_percent": company.xb_layaway_down_percent,
            "xb_layaway_min_payment": company.xb_layaway_min_payment,
            "xb_layaway_cancel_fee_percent": company.xb_layaway_cancel_fee_percent,
        }

    def _xb_layaway_required_down_payment(self):
        """Smallest first payment that lays the goods away."""
        self.ensure_one()
        return self.currency_id.round(self.amount_total * (self.xb_layaway_down_percent or 0.0) / 100.0)

    def _xb_layaway_check_payment(self, amount):
        """Return an error message when ``amount`` is not an acceptable payment on this
        layaway, or False when it is. A payment that settles the balance is always
        accepted; otherwise the first payment must reach the down payment and the next
        ones the minimum payment."""
        self.ensure_one()
        if self.xb_so_kind in ORDER_KINDS:
            return self._xb_order_check_payment(amount)
        if self.xb_so_kind not in LAYAWAY_KINDS:
            return False
        currency = self.currency_id
        if self.xb_layaway_state == "expired":
            return _(
                "Layaway %(name)s expired on %(date)s. Extend its deadline from Sales before "
                "taking more payments.",
                name=self.name, date=format_date(self.env, self.xb_layaway_expired_on),
            )
        if self.xb_layaway_state in ("paid", "cancelled"):
            return _("Layaway %s takes no more payments.", self.name)
        if currency.compare_amounts(amount, 0.0) <= 0:
            return _("The payment must be greater than zero.")
        balance = self.amount_unpaid
        if currency.compare_amounts(amount, balance) > 0:
            return _(
                "The payment (%(amount)s) is higher than the balance of %(name)s (%(balance)s).",
                amount=self._xb_money(amount), name=self.name, balance=self._xb_money(balance),
            )
        if currency.compare_amounts(amount, balance) == 0:
            return False
        if currency.is_zero(self.xb_layaway_paid):
            minimum = self._xb_layaway_required_down_payment()
            if currency.compare_amounts(amount, minimum) < 0:
                return _(
                    "The down payment of %(name)s is at least %(minimum)s (%(percent)s%% of the price).",
                    name=self.name, minimum=self._xb_money(minimum),
                    percent="%g" % float_round(self.xb_layaway_down_percent, 2),
                )
            return False
        minimum = self.xb_layaway_min_payment
        if minimum and currency.compare_amounts(amount, minimum) < 0:
            return _(
                "The minimum payment on %(name)s is %(minimum)s, unless it pays the whole balance (%(balance)s).",
                name=self.name, minimum=self._xb_money(minimum), balance=self._xb_money(balance),
            )
        return False

    def _xb_order_check_payment(self, amount):
        """An order (a special order from the register): its first payment reaches the
        minimum down payment of its company, unless it pays the whole order; then any
        payment up to the balance."""
        self.ensure_one()
        currency = self.currency_id
        if self.state == "cancel":
            return _("Order %s is cancelled.", self.name)
        if currency.compare_amounts(amount, 0.0) <= 0:
            return _("The payment must be greater than zero.")
        balance = self.amount_unpaid
        if currency.compare_amounts(amount, balance) > 0:
            return _(
                "The payment (%(amount)s) is higher than the balance of %(name)s (%(balance)s).",
                amount=self._xb_money(amount), name=self.name, balance=self._xb_money(balance),
            )
        if currency.compare_amounts(amount, balance) == 0 or not currency.is_zero(self.xb_layaway_paid):
            return False
        minimum = self._xb_layaway_required_down_payment()
        if currency.compare_amounts(amount, minimum) < 0:
            return _(
                "The down payment of %(name)s is at least %(minimum)s (%(percent)s%% of the price).",
                name=self.name, minimum=self._xb_money(minimum),
                percent="%g" % float_round(self.xb_layaway_down_percent, 2),
            )
        return False

    def _xb_money(self, amount):
        return formatLang(self.env, amount, currency_obj=self[:1].currency_id or self.env.company.currency_id)

    def _xb_layaway_portal_url(self):
        self.ensure_one()
        return self.get_base_url() + self.get_portal_url()

    # ------------------------------------------------------------------
    # Point of Sale
    # ------------------------------------------------------------------
    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + [
            "xb_layaway_deadline", "xb_layaway_down_percent", "xb_layaway_min_payment",
            "xb_layaway_state", "xb_layaway_expired_on",
        ]

    def _xb_portal_order_url(self):
        self.ensure_one()
        return self.get_base_url() + self.get_portal_url()

    def xb_pos_check_layaway_payment(self, amount):
        """Called by the Point of Sale before it takes a payment on a layaway."""
        self.ensure_one()
        return self.sudo()._xb_layaway_check_payment(amount) or False

    @api.model
    def xb_pos_layaway_holds(self, product_ids, config_id):
        """Layaways holding these goods, for the cashier's warning before selling
        them to someone else. Returns, per product id, the quantity on hand at the
        register's location, the quantity laid away and the layaways holding it."""
        config = self.env["pos.config"].browse(config_id).exists()
        if not config or not config.company_id.xb_layaway_warn_reserved:
            return {}
        products = self.env["product.product"].browse(product_ids or []).exists().filtered(
            lambda p: p.type == "consu" and getattr(p, "is_storable", True)
        )
        if not products:
            return {}
        lines = self.env["sale.order.line"].sudo().search([
            ("product_id", "in", products.ids),
            ("order_id.xb_layaway_state", "in", ("active", "paid")),
            ("order_id.company_id", "child_of", config.company_id.root_id.id),
        ])
        location = config.picking_type_id.default_location_src_id
        result = {}
        for product in products:
            holds = []
            held = 0.0
            for line in lines.filtered(lambda l: l.product_id == product):
                pending = line.product_uom_qty - max(
                    line.qty_delivered,
                    sum(line.pos_order_line_ids.filtered(
                        lambda p: p.order_id.state not in ("draft", "cancel")).mapped("qty")),
                )
                if line.product_uom_id.compare(pending, 0.0) <= 0:
                    continue
                held += pending
                order = line.order_id
                holds.append({
                    "name": order.name,
                    "partner": order.partner_id.name or "",
                    "qty": pending,
                    "deadline": fields.Date.to_string(order.xb_layaway_deadline) if order.xb_layaway_deadline else False,
                    "state": order.xb_layaway_state,
                })
            if not holds:
                continue
            on_hand = product.with_context(location=location.id).qty_available if location else product.qty_available
            result[product.id] = {"on_hand": on_hand, "held": held, "holds": holds}
        return result

    # ------------------------------------------------------------------
    # Daily: expiry (the reminder is an automation rule: data/base_automation_layaway.xml)
    # ------------------------------------------------------------------
    @api.model
    def _xb_cron_layaways(self):
        orders = self.search([
            ("xb_layaway_state", "=", "active"),
            ("xb_layaway_deadline", "!=", False),
        ])
        for order in orders:
            today = order._xb_layaway_today()
            try:
                with self.env.cr.savepoint():
                    if order.xb_layaway_deadline < today:
                        order._xb_layaway_expire()
            except Exception:
                _logger.exception("Layaway %s: daily check failed", order.name)

    def _xb_layaway_expire(self):
        """The deadline passed with a balance: the layaway expires. Nothing is
        refunded automatically (a card can only be refunded the same day it was
        charged, cash only at the counter): the salesperson gets a to-do with what to
        return and what the shop keeps, and the goods stop being held."""
        for order in self:
            order.xb_layaway_expired_on = order._xb_layaway_today()
            fee, refund = order.xb_layaway_fee_amount, order.xb_layaway_refund_amount
            order.message_post(
                body=Markup(
                    "<p>⏰ <b>%(title)s</b></p><ul>"
                    "<li>%(paid_lbl)s %(paid)s</li><li>%(fee_lbl)s %(fee)s</li>"
                    "<li>%(refund_lbl)s %(refund)s</li></ul>"
                ) % {
                    "title": _("Layaway expired unpaid"),
                    "paid_lbl": _("Paid:"), "paid": order._xb_money(order.xb_layaway_paid),
                    "fee_lbl": _("Cancellation fee (%s%%):", "%g" % float_round(order.xb_layaway_cancel_fee_percent, 2)),
                    "fee": order._xb_money(fee),
                    "refund_lbl": _("To return to the customer:"), "refund": order._xb_money(refund),
                },
                subtype_xmlid="mail.mt_note",
            )
            user = order.user_id or order.create_uid
            if user and user.active and not user.share:
                order.xb_layaway_activity_id = order.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=user.id,
                    summary=_("Expired layaway: return %s", order._xb_money(refund)),
                    note=_(
                        "The layaway expired with %(balance)s unpaid. Return %(refund)s to the "
                        "customer (or extend the deadline if they still want it) and cancel "
                        "the order. The shop keeps %(fee)s.",
                        balance=order._xb_money(order.amount_unpaid),
                        refund=order._xb_money(refund), fee=order._xb_money(fee),
                    ),
                )
            if order.company_id.xb_layaway_notify_customer:
                order._xb_layaway_send("xb_sale_order_from_pos.mail_template_layaway_expired")

    def _xb_layaway_send(self, template_xmlid):
        self.ensure_one()
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template or not self.partner_id.email:
            return False
        # Posted as a note addressed to the customer only: the email goes to them and
        # stays in the chatter, without copying every follower of the order.
        self.with_context(mail_notify_force_send=False).message_post_with_source(
            template,
            email_layout_xmlid="mail.mail_notification_light",
            subtype_xmlid="mail.mt_note",
            partner_ids=self.partner_id.ids,
        )
        return True

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def action_xb_layaway_extend(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Extend layaway"),
            "res_model": "xb.layaway.extend",
            "view_mode": "form",
            "target": "new",
            "context": {"default_order_id": self.id},
        }

    def _xb_layaway_set_deadline(self, deadline):
        for order in self:
            if order.xb_so_kind not in LAYAWAY_KINDS:
                raise UserError(_("%s is not a layaway.", order.name))
            if deadline < order._xb_layaway_today():
                raise UserError(_("The new deadline cannot be in the past."))
            was_expired = order.xb_layaway_state == "expired"
            order.write({
                "xb_layaway_deadline": deadline,
                "xb_layaway_expired_on": False,
            })
            if was_expired and order.xb_layaway_activity_id:
                order.xb_layaway_activity_id.unlink()
            order.message_post(
                body=_("Layaway deadline set to %s.", format_date(self.env, deadline)),
                subtype_xmlid="mail.mt_note",
            )


class XbLayawayExtend(models.TransientModel):
    _name = "xb.layaway.extend"
    _description = "Extend a layaway"

    order_id = fields.Many2one("sale.order", required=True, readonly=True)
    deadline = fields.Date(string="New deadline", required=True, default=lambda self: self._default_deadline())

    def _default_deadline(self):
        order = self.env["sale.order"].browse(self.env.context.get("default_order_id")).exists()
        company = order.company_id or self.env.company
        start = max(order.xb_layaway_deadline or order._xb_layaway_today(), order._xb_layaway_today()) if order else fields.Date.context_today(self)
        return start + timedelta(days=company.xb_layaway_days or 30)

    def action_confirm(self):
        self.order_id._xb_layaway_set_deadline(self.deadline)
        return {"type": "ir.actions.act_window_close"}
