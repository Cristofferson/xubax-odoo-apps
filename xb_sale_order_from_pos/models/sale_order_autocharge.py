# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS
# Automatic layaway payments (1.4.0): with the customer's permission, the card they saved
# when paying online pays a fixed amount every week, fortnight or month until the layaway
# is paid. Native payment pieces only: payment.token + payment.transaction on the order
# (the same transaction a payment from «My layaway» creates), so the balance, the
# reconciliation and the provider's own rules are Odoo's.
import logging
import math
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models, modules
from odoo.exceptions import UserError
from odoo.tools.misc import format_date

from .sale_order_layaway import LAYAWAY_KINDS

_logger = logging.getLogger(__name__)

PENDING_TX = ("draft", "pending", "authorized")
MAX_FAILURES = 3   # After this many declines in a row the automatic payments stop.
RETRY_DAYS = 2     # A declined charge is tried again this many days later.

EVERY = [
    ("week", "Every week"),
    ("fortnight", "Every 15 days"),
    ("month", "Every month"),
]


def _step(date, every):
    if every == "week":
        return date + timedelta(days=7)
    if every == "fortnight":
        return date + timedelta(days=15)
    return date + relativedelta(months=1)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    xb_auto_token_id = fields.Many2one(
        "payment.token", string="Card for automatic payments", copy=False, tracking=True,
        help="The customer's saved card that pays this layaway on its own. Empty = no "
        "automatic payments.")
    xb_auto_amount = fields.Monetary(string="Amount per payment", copy=False, tracking=True)
    xb_auto_every = fields.Selection(EVERY, string="How often", copy=False, tracking=True)
    xb_auto_next_date = fields.Date(string="Next automatic payment", copy=False, tracking=True)
    xb_auto_failures = fields.Integer(string="Declined in a row", copy=False, readonly=True)
    xb_auto_authorization = fields.Text(
        string="How the customer authorized it", copy=False,
        help="For example: signed layaway form, WhatsApp of the 3rd, email…")

    # ------------------------------------------------------------------
    # Set up / stop
    # ------------------------------------------------------------------
    def _xb_auto_tokens(self):
        """The customer's saved cards that can pay on their own (the provider saves cards)."""
        self.ensure_one()
        return self.env["payment.token"].sudo().search([
            ("partner_id", "child_of", self.partner_id.commercial_partner_id.id),
            ("active", "=", True),
            ("provider_id.state", "in", ("enabled", "test")),
            ("provider_id.company_id", "in", (False, self.company_id.id)),
        ], order="id desc")

    def action_xb_auto_setup(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Automatic payments"),
            "res_model": "xb.layaway.autocharge",
            "view_mode": "form",
            "target": "new",
            "context": {"default_order_id": self.id},
        }

    def action_xb_auto_stop(self):
        for order in self.filtered("xb_auto_token_id"):
            order._xb_auto_stop(_("Automatic payments stopped by %s.", self.env.user.name))

    def _xb_auto_stop(self, reason):
        for order in self:
            order.write({"xb_auto_token_id": False, "xb_auto_next_date": False, "xb_auto_failures": 0})
            order.message_post(body=reason, subtype_xmlid="mail.mt_note")

    # ------------------------------------------------------------------
    # Charging
    # ------------------------------------------------------------------
    def _xb_auto_charge(self):
        """One automatic payment: the amount agreed, or the balance when it is less.
        Returns the transaction, or None when nothing was charged."""
        self.ensure_one()
        cur = self.currency_id
        balance = self.amount_unpaid
        if cur.compare_amounts(balance, 0.0) <= 0:
            self._xb_auto_stop(_("Layaway paid: automatic payments finished."))
            return None
        if self.transaction_ids.filtered(lambda t: t.state in PENDING_TX):
            return None  # A payment is on its way: wait for it.
        amount = cur.round(min(self.xb_auto_amount or balance, balance))
        token = self.xb_auto_token_id.sudo()
        tx = self.env["payment.transaction"].sudo().create({
            "provider_id": token.provider_id.id,
            "payment_method_id": token.payment_method_id.id,
            "amount": amount,
            "currency_id": cur.id,
            "partner_id": self.partner_id.id,
            "token_id": token.id,
            "operation": "offline",
            "sale_order_ids": [(6, 0, self.ids)],
        })
        try:
            tx._charge_with_token()
        except Exception as error:  # The provider said no or did not answer.
            _logger.warning("Layaway %s: automatic payment failed: %s", self.name, error)
            if tx.state in PENDING_TX:
                tx._set_error(str(error))
        if tx.state == "done":
            tx._post_process()
        today = self._xb_layaway_today()
        if tx.state == "error":
            self.xb_auto_failures += 1
            reason = tx.state_message or _("no reason given")
            if self.xb_auto_failures >= MAX_FAILURES:
                self._xb_auto_stop(_("Card declined %(times)s times in a row: automatic payments stopped (%(reason)s).",
                                     times=self.xb_auto_failures, reason=reason))
                self._xb_auto_todo(_("Automatic payments stopped: card declined"))
            else:
                self.xb_auto_next_date = today + timedelta(days=RETRY_DAYS)
                self.message_post(body=_("The card was declined for %(amount)s: %(reason)s. It will be tried again on %(date)s.",
                                         amount=self._xb_money(amount), reason=reason,
                                         date=format_date(self.env, self.xb_auto_next_date)),
                                  subtype_xmlid="mail.mt_note")
                self._xb_auto_todo(_("Card declined on the layaway's automatic payment"))
            return tx
        self.xb_auto_failures = 0
        self.message_post(body=_("Automatic payment of %(amount)s charged to %(card)s.",
                                 amount=self._xb_money(amount), card=token.display_name),
                          subtype_xmlid="mail.mt_note")
        if tx.state == "done":
            self._xb_layaway_send("xb_sale_order_from_pos.mail_template_layaway_autocharge")
        if cur.compare_amounts(self.amount_unpaid, 0.0) <= 0:
            self._xb_auto_stop(_("Layaway paid: automatic payments finished."))
        else:
            self.xb_auto_next_date = _step(max(self.xb_auto_next_date or today, today), self.xb_auto_every)
        return tx

    def _xb_auto_todo(self, summary):
        self.ensure_one()
        user = self.user_id or self.create_uid
        if user and user.active and not user.share and not self.activity_ids.filtered(lambda a: a.summary == summary):
            self.activity_schedule("mail.mail_activity_data_todo", user_id=user.id, summary=summary,
                                   note=_("Ask the customer for another card or to pay at the shop or online."))

    @api.model
    def _xb_cron_autocharge(self):
        orders = self.sudo().search([
            ("xb_so_kind", "in", LAYAWAY_KINDS),
            ("xb_layaway_state", "=", "active"),
            ("xb_auto_token_id", "!=", False),
            ("xb_auto_next_date", "!=", False),
        ])
        for order in orders:
            order = order.with_company(order.company_id)
            if order.xb_auto_next_date > order._xb_layaway_today():
                continue
            try:
                with self.env.cr.savepoint():
                    order._xb_auto_charge()
            except Exception:
                _logger.exception("Layaway %s: automatic payment failed", order.name)
            if not modules.module.current_test:
                self.env.cr.commit()  # One customer's payment is kept even if the next one fails.

    @api.model
    def _xb_cron_layaways(self):
        # Charge first, so a payment due on the last day counts before the expiry check.
        self._xb_cron_autocharge()
        return super()._xb_cron_layaways()

    def _xb_layaway_expire(self):
        result = super()._xb_layaway_expire()
        self.filtered("xb_auto_token_id")._xb_auto_stop(_("Layaway expired: automatic payments stopped."))
        return result

    def _action_cancel(self):
        result = super()._action_cancel()
        self.filtered("xb_auto_token_id")._xb_auto_stop(_("Order cancelled: automatic payments stopped."))
        return result


class XbLayawayAutocharge(models.TransientModel):
    _name = "xb.layaway.autocharge"
    _description = "Automatic layaway payments"

    order_id = fields.Many2one("sale.order", required=True, readonly=True)
    currency_id = fields.Many2one(related="order_id.currency_id")
    balance = fields.Monetary(related="order_id.amount_unpaid", string="Balance")
    deadline = fields.Date(related="order_id.xb_layaway_deadline")
    token_ids = fields.Many2many("payment.token", compute="_compute_token_ids")
    token_id = fields.Many2one("payment.token", string="Saved card", domain="[('id', 'in', token_ids)]")
    every = fields.Selection(EVERY, string="How often", required=True, default="fortnight")
    first_date = fields.Date(string="First payment", required=True,
                             default=lambda self: self._default_first_date(),
                             help="Today = charged as soon as you confirm. Later dates are charged that morning.")
    amount = fields.Monetary(string="Amount per payment")
    authorization = fields.Text(string="How the customer authorized it")
    summary = fields.Char(compute="_compute_summary")

    def _xb_target_order(self):
        return self.env["sale.order"].browse(self.env.context.get("default_order_id")).exists()

    def _default_first_date(self):
        order = self._xb_target_order()
        today = order._xb_layaway_today() if order else fields.Date.context_today(self)
        return order.xb_auto_next_date or today if order else today

    @api.depends("order_id")
    def _compute_token_ids(self):
        for wizard in self:
            wizard.token_ids = wizard.order_id._xb_auto_tokens() if wizard.order_id else False

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        order = self._xb_target_order()
        if order:
            token = order.xb_auto_token_id or order._xb_auto_tokens()[:1]
            values.setdefault("token_id", token.id)
            values.setdefault("every", order.xb_auto_every or "fortnight")
            values.setdefault("authorization", order.xb_auto_authorization)
            values.setdefault("amount", order.xb_auto_amount or self._suggest(
                order, values.get("every") or "fortnight", values.get("first_date") or self._default_first_date()))
        return values

    @api.model
    def _charges_until(self, order, every, first):
        """How many payments fit from ``first`` to the deadline (at least one)."""
        count, date = 0, first
        while order.xb_layaway_deadline and date <= order.xb_layaway_deadline and count < 60:
            count, date = count + 1, _step(date, every)
        return max(count, 1)

    @api.model
    def _suggest(self, order, every, first):
        """An even amount that pays the balance by the deadline, rounded up to the peso."""
        balance = order.amount_unpaid
        amount = math.ceil(balance / self._charges_until(order, every, first))
        amount = max(amount, order.xb_layaway_min_payment or 0.0)
        return min(amount, balance)

    @api.onchange("every", "first_date")
    def _onchange_every(self):
        if self.order_id and self.first_date:
            self.amount = self._suggest(self.order_id, self.every, self.first_date)

    @api.depends("amount", "every", "first_date", "order_id")
    def _compute_summary(self):
        for wizard in self:
            order = wizard.order_id
            if not (order and wizard.amount and wizard.first_date and order.xb_layaway_deadline):
                wizard.summary = False
                continue
            covered = wizard.amount * wizard._charges_until(order, wizard.every, wizard.first_date)
            short = order.amount_unpaid - covered
            wizard.summary = _("By the deadline %(left)s would still be owed.", left=order._xb_money(short)) \
                if order.currency_id.compare_amounts(short, 0.0) > 0 else \
                _("The balance is paid by the deadline.")

    def action_confirm(self):
        self.ensure_one()
        order = self.order_id
        if order.xb_so_kind not in LAYAWAY_KINDS or order.xb_layaway_state != "active":
            raise UserError(_("Automatic payments are for active layaways (with their down payment)."))
        if not self.token_id:
            raise UserError(_("The customer has no saved card yet. Send them the link to their layaway: when they "
                              "pay online, they tick «Save my payment details»."))
        if self.token_id not in order._xb_auto_tokens():
            raise UserError(_("That card is not the customer's."))
        cur = order.currency_id
        if cur.compare_amounts(self.amount, 0.0) <= 0:
            raise UserError(_("Write the amount of each payment."))
        if cur.compare_amounts(self.amount, order.xb_layaway_min_payment) < 0 \
                and cur.compare_amounts(self.amount, order.amount_unpaid) < 0:
            raise UserError(_("Each payment must be at least the layaway's minimum payment (%s).",
                              order._xb_money(order.xb_layaway_min_payment)))
        if self.first_date < order._xb_layaway_today():
            raise UserError(_("The first payment cannot be in the past."))
        order.write({
            "xb_auto_token_id": self.token_id.id,
            "xb_auto_amount": self.amount,
            "xb_auto_every": self.every,
            "xb_auto_next_date": self.first_date,
            "xb_auto_failures": 0,
            "xb_auto_authorization": self.authorization,
        })
        order.message_post(body=_("Automatic payments: %(amount)s %(every)s to %(card)s, from %(date)s.",
                                  amount=order._xb_money(self.amount),
                                  every=dict(self._fields["every"]._description_selection(self.env))[self.every].lower(),
                                  card=self.token_id.display_name, date=format_date(self.env, self.first_date)),
                           subtype_xmlid="mail.mt_note")
        if self.first_date <= order._xb_layaway_today():
            order._xb_auto_charge()  # First payment today: charged now, not at tomorrow's run.
        return {"type": "ir.actions.act_window_close"}
