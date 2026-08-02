# -*- coding: utf-8 -*-
"""The commercial side: what each store has bought, and billing it.

This is what turns the business model into something operated rather than
remembered. Each store carries a plan, a trial, and a link to the recurring
sale order that bills it.

Two deliberate choices worth stating
------------------------------------
**The plan is a configuration control, not a licence.** The brief says so
explicitly, and it is the right call: a hard licence check inside the code
would mean a billing hiccup on our side turns a customer's cameras off, and it
would mean every future feature has to be written twice — once for the feature
and once for the enforcement. What the plan does is decide what the store's
users *see and can switch on*. A customer on the counting plan does not get
lost-sale alerts because those switches are hidden, not because an exception is
raised at 3 a.m.

**The subscription is a ``sale.order``.** In Odoo 17 and later a subscription
*is* a sale order carrying a recurring plan; ``sale.subscription`` no longer
exists as a model. That is fortunate here, because ``sale.order`` is Community
while the recurring machinery is Enterprise: the link works everywhere, gives a
proper picker, and the recurring fields are read defensively so a Community
instance simply shows a plain order.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

#: What each plan switches on. The names are the store fields the plan governs.
PLAN_FEATURES = {
    "counting": [],
    "insight": ["reid_enabled", "demographics_enabled",
                "group_detection_enabled"],
    "floor": ["reid_enabled", "demographics_enabled",
              "group_detection_enabled", "lost_sale_enabled",
              "checkout_match_enabled", "anomaly_detection_enabled"],
    "full": ["reid_enabled", "demographics_enabled",
             "group_detection_enabled", "lost_sale_enabled",
             "checkout_match_enabled", "anomaly_detection_enabled",
             "signage_enabled", "identify_customers", "attendance_enabled"],
}


class AnalitixStoreSubscription(models.Model):
    _inherit = "analitix.store"

    plan = fields.Selection(
        selection=[
            ("counting", "Counting"),
            ("insight", "Counting + Insight"),
            ("floor", "Insight + Floor"),
            ("full", "Full"),
        ],
        string="Plan", default="counting", required=True, tracking=True,
        help="What this store has contracted. It governs which features their "
             "users can see and switch on — it is not a licence check in the "
             "code, so a billing problem can never switch a customer's cameras "
             "off.")
    subscription_order_id = fields.Many2one(
        "sale.order", string="Subscription", ondelete="set null", tracking=True,
        help="The recurring sale order that bills this store. On Odoo "
             "Enterprise this is a subscription with a recurring plan; on "
             "Community it is an ordinary order and the recurrence is handled "
             "however the customer already handles it.")
    subscription_state = fields.Selection(
        selection=[
            ("trial", "Trial"),
            ("active", "Active"),
            ("paused", "Paused"),
            ("cancelled", "Cancelled"),
        ],
        string="Billing Status", default="trial", required=True, index=True,
        tracking=True)
    trial_end_date = fields.Date(
        string="Trial Ends", tracking=True,
        help="After this the store is expected to be on a paid plan. Nothing "
             "stops working on its own: an expired trial raises an activity "
             "for a human, because cutting a customer off automatically over a "
             "date is how you lose one who was about to sign.")
    activated_on = fields.Date(string="Live Since", tracking=True)
    monthly_fee = fields.Monetary(
        string="Monthly Fee", currency_field="currency_id",
        help="Recorded here for the value report, which compares it against "
             "the revenue the store recovered.")
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True)

    @api.onchange("plan")
    def _onchange_plan(self):
        """Show the customer what their plan actually turns on.

        Applied as an onchange rather than a constraint so an implementer can
        still override an individual switch afterwards — a customer piloting one
        feature outside their plan is a sales conversation, not an error.
        """
        for store in self:
            features = PLAN_FEATURES.get(store.plan, [])
            for field in set(sum(PLAN_FEATURES.values(), [])):
                if field in store._fields:
                    store[field] = field in features

    def action_start_trial(self, days=30):
        """Begin a trial. The length is an argument because it is negotiated."""
        for store in self:
            store.write({
                "subscription_state": "trial",
                "trial_end_date": fields.Date.add(
                    fields.Date.context_today(store), days=days),
            })
            store.message_post(body=_(
                "Trial started, ending %s.", store.trial_end_date))
        return True

    def action_activate(self):
        for store in self:
            store.write({
                "subscription_state": "active",
                "activated_on": fields.Date.context_today(store),
            })
            store.message_post(body=_("Subscription active."))
        return True

    def action_pause_subscription(self):
        """Pause billing. Deliberately does NOT pause capture.

        A customer who pauses their subscription has not asked to lose the
        history they already paid for, and stopping the cameras would make the
        month they come back read as a catastrophic collapse in traffic. The
        capture kill switch is a separate, explicit control.
        """
        for store in self:
            store.write({"subscription_state": "paused"})
            store.message_post(body=_(
                "Subscription paused. Data capture is unaffected — use the "
                "capture switch if it should stop too."))
        return True

    def action_cancel_subscription(self):
        for store in self:
            store.write({"subscription_state": "cancelled"})
            store.message_post(body=_("Subscription cancelled."))
        return True

    # ------------------------------------------------------------------
    @api.model
    def _cron_check_trials(self):
        """Tell a human when a trial has run out. Never cut anybody off."""
        today = fields.Date.context_today(self)
        expiring = self.sudo().search([
            ("subscription_state", "=", "trial"),
            ("trial_end_date", "!=", False),
            ("trial_end_date", "<=", today),
        ])
        for store in expiring:
            responsible = store.alert_user_id or store.create_uid
            try:
                store.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Analitix trial ended: %s", store.name),
                    note=_(
                        "The trial for <b>%(store)s</b> ended on %(date)s. "
                        "Nothing has been switched off — decide with the "
                        "customer whether to activate, extend or close it.",
                        store=store.name, date=store.trial_end_date),
                    user_id=responsible.id)
            except ValueError:
                _logger.warning(
                    "Analitix: could not raise a trial activity for store %s.",
                    store.id)
        return True

    def _is_billable(self):
        """Whether this store should appear on this month's invoicing run."""
        self.ensure_one()
        return self.subscription_state == "active" and self.monthly_fee > 0
