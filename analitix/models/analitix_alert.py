# -*- coding: utf-8 -*-
"""The discreet nudge — built once here, reused by every phase that needs it.

"Discreet" has a precise meaning in this product, and it is a constraint on the
implementation rather than a description of it: **only the assigned salesperson
perceives the alert. Never the customer, never the rest of the floor.**

Channels
--------
Five independent switches, because a store may well want two or three at once
and forcing a single choice made the common combinations impossible.

**Discreet** — only the assigned salesperson perceives them:

* **Odoo mobile app** (default): a ``bus.bus`` push for the banner and buzz in
  their pocket, plus an activity so it survives a locked screen.
* **Odoo chat (Discuss)**: a one-to-one message, which on a floor where the
  team keeps Discuss open all day is often read faster than a push. Odoo's own
  client chimes for it — audible on their device, not in the shop.
* **WhatsApp**: for staff who do not keep the Odoo app open. Through the native
  ``whatsapp`` module, detected at runtime, so Analitix does not depend on it.

**Not discreet** — off by default, and labelled with the consequence rather
than hidden:

* **Audible chime**: if the phone is not on silent, or the alert lands on a
  back-office machine, the customer may hear it and understand that they are
  being discussed.
* **Signage screen**: whatever appears there is read by the customer standing
  in front of it. Fine for a message written *for* them ("ask about our finance
  options"), wrong for one *about* them.

The original brief excluded those last two outright. The shop owner asked for
them, and it is their floor: what this code owes them is that the consequence
is stated in the field's own help text rather than discovered in front of a
customer. Phase 4 builds the full per-player signage engine on the same zone
mapping.

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

from markupsafe import Markup, escape

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
    # One flag per channel rather than a single field: an alert genuinely can go
    # out on three at once, and recording only "the" channel would make the
    # delivery report a guess. Filterable, unlike a comma-separated string.
    sent_app = fields.Boolean(string="Sent To App", readonly=True)
    sent_discuss = fields.Boolean(string="Sent To Chat", readonly=True)
    sent_whatsapp = fields.Boolean(string="Sent To WhatsApp", readonly=True)
    sent_sound = fields.Boolean(string="Chimed", readonly=True)
    sent_screen = fields.Boolean(string="Shown On Screen", readonly=True)
    delivered = fields.Boolean(
        string="Delivered", compute="_compute_channel", store=True, index=True,
        help="At least one channel accepted it. False means the alert was "
             "recorded but never reached anybody — usually no recipient, or a "
             "channel that is switched on but not configured.")
    channel_summary = fields.Char(
        string="Channels", compute="_compute_channel", store=True,
        help="Which channels actually delivered this alert.")
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

    @api.depends("sent_app", "sent_discuss", "sent_whatsapp", "sent_sound",
                 "sent_screen")
    def _compute_channel(self):
        labels = [
            ("sent_app", _("app")),
            ("sent_discuss", _("chat")),
            ("sent_whatsapp", _("WhatsApp")),
            ("sent_sound", _("chime")),
            ("sent_screen", _("screen")),
        ]
        for alert in self:
            used = [label for field, label in labels if alert[field]]
            alert.channel_summary = (
                ", ".join(used) if used else _("not delivered"))
            alert.delivered = bool(used)

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
        """Send on every channel the store has switched on.

        Each channel is attempted independently and failures are isolated: a
        store with no WhatsApp template still gets the app push, and the alert
        records exactly what reached anybody rather than claiming a delivery it
        did not make.
        """
        self.ensure_one()
        vals = {}
        if store.alert_use_app:
            vals["sent_app"] = self._push_to_app(recipient, store)
        if store.alert_use_discuss:
            vals["sent_discuss"] = self._push_to_discuss(recipient)
        if store.alert_use_whatsapp:
            vals["sent_whatsapp"] = self._push_to_whatsapp(recipient)
        if store.alert_use_sound:
            # Recorded as its own channel because it is a real change in what
            # the shop sounds like, and someone reviewing the alert log later
            # should be able to see when it was on.
            vals["sent_sound"] = bool(vals.get("sent_app")
                                      or vals.get("sent_discuss"))
        if store.alert_use_screen:
            vals["sent_screen"] = self._push_to_screen(store)

        self.sudo().write(vals)
        return any(vals.values())

    def _push_to_app(self, recipient, store=None):
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
                    # The client decides whether to make a noise. Carried in the
                    # payload rather than assumed, so the store's setting is
                    # what governs it rather than the device's defaults.
                    "sound": bool(store and store.alert_use_sound),
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

    def _push_to_discuss(self, recipient):
        """A direct message in Odoo's own chat.

        Often the fastest channel in practice: on a floor where the team keeps
        Discuss open all day, a message lands where they are already looking,
        and Odoo's client chimes for it natively — audible on the salesperson's
        device without being audible in the shop.

        Uses a one-to-one chat rather than a group so it stays discreet: the
        rest of the floor never sees it.
        """
        self.ensure_one()
        if not recipient._is_internal():
            # Discuss is for internal users. A portal or shared recipient
            # cannot be reached this way, and saying so plainly beats an
            # access-rights traceback that looks like a bug in Analitix.
            _logger.info(
                "Analitix: %s is not an internal user, so the Discuss channel "
                "cannot reach them.", recipient.display_name)
            return False
        try:
            # _get_or_create_chat puts the *calling* user in the chat, so the
            # conversation has to be opened as OdooBot: the message comes from
            # the system, not from whichever cashier happened to trigger it.
            #
            # Order matters — with_user() forces su=False even for the
            # superuser, so sudo() has to come after it or the channel lookup
            # is refused.
            Channel = self.env["discuss.channel"].with_user(
                self.env.ref("base.user_root")).sudo()
            chat = Channel._get_or_create_chat(
                partners_to=[recipient.partner_id.id])
            if not chat:
                return False
            # Markup, not a plain string with tags in it. ``message_post``
            # escapes a plain str, so the salesperson was reading a literal
            # "<br/>" in the middle of the sentence — every Discuss alert since
            # this channel was added. Each piece is escaped on its own and the
            # breaks are the only markup, so a zone somebody named
            # "Rings & Watches" cannot inject anything.
            lines = [self.summary]
            if self.body:
                lines.extend(self.body.split("\n"))
            body = Markup("<br/>").join(escape(line) for line in lines)
            chat.sudo().message_post(
                body=body,
                message_type="comment",
                subtype_xmlid="mail.mt_comment")
            return True
        except Exception as error:  # noqa: BLE001
            _logger.warning(
                "Analitix: Discuss alert %s failed: %s", self.id, error)
            return False

    def _push_to_screen(self, store):
        """Put the alert on the signage screen covering the zone.

        **This channel is not discreet and the UI says so.** Whatever appears
        here is read by the customer standing in front of it, so it is off by
        default and its help text spells out the consequence. The store owner
        decides how their own floor works; what this code owes them is that the
        consequence is stated plainly rather than discovered.

        The delivery itself lives on ``analitix.zone`` because the signage rule
        engine needs exactly the same thing — one implementation, two callers.
        """
        self.ensure_one()
        ok, error = self.env["analitix.zone"]._send_to_screen(
            self.zone_id, self.summary,
            layout_ref=store.alert_screen_layout_ref,
            seconds=store.alert_screen_seconds)
        if error and not ok:
            _logger.info("Analitix: alert %s not shown on screen: %s",
                         self.id, error)
        return ok

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
