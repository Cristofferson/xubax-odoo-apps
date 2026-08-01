# -*- coding: utf-8 -*-
"""The discreet nudge — built once here, reused by every phase that needs it.

"Discreet" has a precise meaning in this product, and it is a constraint on the
implementation rather than a description of it: **only the assigned salesperson
perceives the alert. Never the customer, never the rest of the floor.**

What that rules out, permanently
--------------------------------
* Anything audible — a chime, a buzzer, a bell. The customer hears it, knows
  they are being discussed, and the shop feels like a surveillance operation.
* Anything the customer can see: a message on a Xibo screen, a light on the
  floor. Phase 4 sends plenty to the screens, but never *this*.

Those are not configuration options. There is no channel field value for them,
so a well-meaning implementer cannot switch one on later.

What it allows
--------------
* **The Odoo mobile app** (default): a ``bus.bus`` push for the banner and
  buzz in the salesperson's pocket, plus an activity so it survives a locked
  screen and is still there when they check.
* **WhatsApp** (optional), through the same native ``whatsapp`` module the
  special-dates addon already uses. Detected at runtime — Analitix does not
  depend on it, so a store without WhatsApp simply never sees the option.

Routing
-------
An alert without a named recipient is a notification nobody owns. Recipients
come from the zone→salesperson map *for the moment the alert fires*, because
who covers the jewellery counter at 11:00 is not who covers it at 19:00. If
nobody is on duty there, it escalates to the store's fallback user rather than
evaporating.

Every alert is recorded — who, when, which channel, whether they reacted — and
that record is what phase 4's floor-coaching report is computed from. An alert
that is not stored cannot be measured, and a nudge nobody measures is a nudge
nobody improves.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AnalitixAlert(models.Model):
    _name = "analitix.alert"
    _description = "Analitix Discreet Alert"
    _order = "sent_at desc, id desc"
    _rec_name = "summary"

    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)
    zone_id = fields.Many2one(
        "analitix.zone", string="Zone", index=True, ondelete="set null")
    visitor_id = fields.Many2one(
        "analitix.visitor", string="Visit", index=True, ondelete="set null")
    partner_id = fields.Many2one(
        "res.partner", string="Customer", index=True, ondelete="set null",
        help="Set only for a recognised, identified customer. Most alerts carry "
             "no identity at all.")

    kind = fields.Selection(
        selection=[
            ("lost_sale", "Possible lost sale"),
            ("known_customer", "Known customer arrived"),
            ("anomaly", "Unusual behaviour"),
            ("emotion", "Customer looks unhappy"),
            ("watchlist", "Watch-list match"),
            ("other", "Other"),
        ],
        string="Type", required=True, index=True)
    summary = fields.Char(
        string="Message", required=True,
        help="What the salesperson actually reads, on a phone, mid-shift. Short "
             "enough to take in at a glance and act on without opening it.")
    body = fields.Text(string="Detail")

    user_id = fields.Many2one(
        "res.users", string="Recipient", index=True, ondelete="set null")
    was_fallback = fields.Boolean(
        string="Escalated",
        help="Nobody was on duty in that zone, so this went to the store's "
             "fallback. A lot of these means the shift map is wrong.")
    channel = fields.Selection(
        selection=[
            ("bus", "Mobile app"),
            ("whatsapp", "WhatsApp"),
            ("both", "Mobile app + WhatsApp"),
            ("none", "Not delivered"),
        ],
        string="Channel", default="bus", required=True)
    sent_at = fields.Datetime(
        string="Sent", required=True, index=True,
        default=lambda self: fields.Datetime.now())

    acknowledged = fields.Boolean(string="Acknowledged", index=True)
    acknowledged_at = fields.Datetime(string="Acknowledged At", readonly=True)
    response_seconds = fields.Integer(
        string="Response (s)", compute="_compute_response", store=True,
        help="How long the salesperson took to acknowledge. The number that "
             "tells an owner whether the nudges are actually being read.")
    outcome = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("attended", "Attended"),
            ("sold", "Ended in a sale"),
            ("missed", "Not attended"),
        ],
        string="Outcome", default="pending", index=True,
        help="Filled in by the salesperson, or by phase 4 when a sale is "
             "matched to the same visit shortly afterwards.")

    _store_sent_idx = models.Index("(store_id, sent_at DESC)")

    @api.depends("sent_at", "acknowledged_at")
    def _compute_response(self):
        for alert in self:
            if alert.sent_at and alert.acknowledged_at:
                alert.response_seconds = int(
                    (alert.acknowledged_at - alert.sent_at).total_seconds())
            else:
                alert.response_seconds = 0

    # ------------------------------------------------------------------
    # Raising an alert
    # ------------------------------------------------------------------
    @api.model
    def raise_alert(self, store, kind, summary, body=None, zone=None,
                    visitor=None, partner=None, user=None):
        """Create and deliver one discreet alert. Returns it, or an empty set.

        Never raises: an alerting path that can throw would take down the
        counting pipeline it hangs off, and the whole architecture is built so
        that an outbound integration failing never stops data capture.
        """
        try:
            recipient, was_fallback = (
                (user, False) if user else self._resolve_recipient(store, zone))
            if not recipient:
                _logger.info(
                    "Analitix: no recipient for a %s alert at store %s; "
                    "recording it undelivered.", kind, store.display_name)

            if recipient and self._is_muted(store, recipient, kind, zone):
                # Deliberately silent: a salesperson buzzed every ninety seconds
                # stops reading the alerts entirely, which is worse than not
                # sending them.
                return self.browse()

            alert = self.sudo().create({
                "store_id": store.id,
                "zone_id": zone.id if zone else False,
                "visitor_id": visitor.id if visitor else False,
                "partner_id": partner.id if partner else False,
                "kind": kind,
                "summary": summary[:255],
                "body": body,
                "user_id": recipient.id if recipient else False,
                "was_fallback": was_fallback,
                "channel": "none",
            })
            if recipient:
                alert._deliver(store, recipient)
            return alert
        except Exception:  # noqa: BLE001
            _logger.exception("Analitix: could not raise a %s alert.", kind)
            return self.browse()

    @api.model
    def _resolve_recipient(self, store, zone):
        """Who is covering ``zone`` right now — or the store's fallback."""
        if zone:
            on_duty = self.env["analitix.zone.vendor"].sudo()._covering(zone)
            if on_duty:
                # One recipient, not all of them: "discreet" means one person
                # is nudged, not that the whole floor is told about a customer.
                # Least recently alerted, so the load spreads.
                return on_duty[0], False
        return store.alert_fallback_user_id, bool(zone)

    @api.model
    def _is_muted(self, store, recipient, kind, zone):
        """True when this person was already nudged about this very recently."""
        if store.alert_cooldown_minutes <= 0:
            return False
        since = fields.Datetime.now() - timedelta(
            minutes=store.alert_cooldown_minutes)
        domain = [
            ("store_id", "=", store.id),
            ("user_id", "=", recipient.id),
            ("kind", "=", kind),
            ("sent_at", ">=", since),
        ]
        if zone:
            domain.append(("zone_id", "=", zone.id))
        return bool(self.sudo().search_count(domain))

    def _deliver(self, store, recipient):
        """Push to the app, and to WhatsApp when the store asked for it."""
        self.ensure_one()
        delivered = []

        if store.alert_channel in ("bus", "both"):
            if self._push_to_app(recipient):
                delivered.append("bus")

        if store.alert_channel in ("whatsapp", "both"):
            if self._push_to_whatsapp(recipient):
                delivered.append("whatsapp")

        channel = "none"
        if len(delivered) == 2:
            channel = "both"
        elif delivered:
            channel = delivered[0]
        self.sudo().channel = channel
        return channel != "none"

    def _push_to_app(self, recipient):
        """bus.bus for the buzz, an activity so it survives a locked screen."""
        self.ensure_one()
        ok = False
        try:
            self.env["bus.bus"]._sendone(
                recipient.partner_id, "analitix.alert", {
                    "id": self.id,
                    "kind": self.kind,
                    "summary": self.summary,
                    "zone": self.zone_id.name or "",
                    "store": self.store_id.name,
                })
            ok = True
        except Exception:  # noqa: BLE001
            _logger.warning("Analitix: bus push failed for alert %s.", self.id)
        try:
            self.activity_schedule_alert(recipient)
            ok = True
        except Exception:  # noqa: BLE001
            _logger.warning("Analitix: activity failed for alert %s.", self.id)
        return ok

    def activity_schedule_alert(self, recipient):
        """A to-do on the store, not on the alert.

        Deliberate: a salesperson's Odoo activity list should read like their
        shop's work, not like a stream of technical records they have never
        heard of.
        """
        self.ensure_one()
        self.env["mail.activity"].sudo().create({
            "res_model_id": self.env["ir.model"]._get_id("analitix.store"),
            "res_id": self.store_id.id,
            "activity_type_id": self.env.ref("mail.mail_activity_data_todo").id,
            "summary": self.summary,
            "note": self.body or self.summary,
            "user_id": recipient.id,
            "date_deadline": fields.Date.context_today(self),
        })

    def _push_to_whatsapp(self, recipient):
        """Optional channel, detected at runtime.

        Analitix does not depend on the ``whatsapp`` module: this is sold to
        stores that may not have it, and a hard dependency would make the app
        uninstallable for them. Absent the module, the option simply does
        nothing and the app push has already carried the message.
        """
        self.ensure_one()
        installed = self.env["ir.module.module"].sudo().search_count(
            [("name", "=", "whatsapp"), ("state", "=", "installed")])
        if not installed:
            return False
        number = recipient.partner_id.mobile or recipient.partner_id.phone
        if not number:
            return False
        template_id = self.store_id.alert_whatsapp_template_id
        if not template_id:
            return False
        template = self.env["whatsapp.template"].sudo().browse(
            template_id).exists()
        if not template:
            _logger.warning(
                "Analitix: store %s points at WhatsApp template %s, which does "
                "not exist.", self.store_id.display_name, template_id)
            return False
        try:
            composer = self.env["whatsapp.composer"].sudo().create({
                "wa_template_id": template.id,
                "res_model": "analitix.alert",
                "res_ids": str(self.id),
                "phone": number,
            })
            composer._send_whatsapp_template()
            return True
        except Exception as error:  # noqa: BLE001
            _logger.warning(
                "Analitix: WhatsApp alert %s failed: %s", self.id, error)
            return False

    # ------------------------------------------------------------------
    def action_acknowledge(self):
        """The salesperson says 'seen, I am going'."""
        for alert in self:
            alert.sudo().write({
                "acknowledged": True,
                "acknowledged_at": fields.Datetime.now(),
                "outcome": "attended" if alert.outcome == "pending"
                           else alert.outcome,
            })
        return True

    @api.model
    def _cron_mark_missed(self):
        """Alerts nobody acknowledged become evidence, not noise.

        Without this the coaching report of phase 4 would only ever see the
        alerts that went well, which is the most flattering and least useful
        version of the truth.
        """
        for store in self.env["analitix.store"].sudo().search([]):
            cutoff = fields.Datetime.now() - timedelta(
                minutes=max(store.alert_missed_after_minutes, 1))
            self.sudo().search([
                ("store_id", "=", store.id),
                ("acknowledged", "=", False),
                ("outcome", "=", "pending"),
                ("sent_at", "<", cutoff),
            ]).write({"outcome": "missed"})
        return True
