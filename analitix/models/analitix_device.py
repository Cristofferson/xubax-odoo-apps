# -*- coding: utf-8 -*-
"""An edge device: the only thing allowed to talk to the ingest API.

Credentials (task 984, point 4)
-------------------------------
Each device carries its own key — never one shared across a fleet, because a
shared key cannot be revoked without bricking every other camera.  The key is
shown **once**, at creation or rotation, and only its SHA-256 digest is stored.
That means:

* a database dump does not hand an attacker a working key;
* nobody, including an administrator, can read a key back out of Odoo — losing
  it means rotating it, which is the correct trade;
* revocation is instant and is a data change, not a deployment: archive the
  device or hit *Revoke*, and the very next request is rejected.

A device key authorises exactly two things: posting events for **its own**
store, and reading **its own** configuration.  It is not a login, it opens no
business data, and it cannot reach another store's records.

Health (task 982, point 1)
--------------------------
The agent heartbeats on the interval its store configures.  ``status`` is a
stored field maintained both on arrival (a heartbeat marks the device online at
once) and by cron (nothing arriving is exactly what has to be detected, and no
inbound request will ever tell us that).
"""
import hashlib
import logging
import secrets
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

KEY_PREFIX = "alx"

#: Events a device must have produced in the past week before its volume is
#: judged at all. Below this there is no "normal" to deviate from.
MIN_HISTORY_EVENTS = 100
#: Absolute floor for an anomaly, on top of the per-device ratio. Keeps quiet
#: stores from generating alerts over ordinary noise.
MIN_ANOMALY_EVENTS = 20

#: Below this hourly baseline a device is too quiet to judge as blind. A service
#: door that sees four people a day would otherwise be reported dead every
#: lunchtime, and an alert that cries wolf is an alert nobody reads.
MIN_BLIND_BASELINE = 3.0


def hash_key(raw_key):
    """Return the digest stored for ``raw_key``.

    Plain SHA-256, not a password hash: an API key is 256 bits of machine-made
    randomness, so there is no dictionary to attack and no reason to pay
    bcrypt's cost on the hot ingest path — a store's fleet hits this on every
    single crossing.
    """
    return hashlib.sha256((raw_key or "").encode()).hexdigest()


class AnalitixDevice(models.Model):
    _name = "analitix.device"
    _description = "Analitix Edge Device"
    # activity.mixin as well as thread: an offline critical device schedules an
    # activity on itself, which is what puts it in a human's Odoo to-do list
    # rather than only in a log nobody reads.
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "store_id, door_id, name"

    name = fields.Char(required=True, tracking=True)
    device_uid = fields.Char(
        string="Device UID", required=True, copy=False, index=True,
        help="Stable identifier the agent sends in every payload, e.g. "
             "'mor01-north-counter'. It identifies the device in logs; it does "
             "not authenticate it — the API key does.")
    active = fields.Boolean(default=True, tracking=True)

    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="restrict",
        help="The only store this device may ever post data for.")
    door_id = fields.Many2one(
        "analitix.door", string="Door", index=True, ondelete="set null",
        domain="[('store_id', '=', store_id)]",
        help="Which entrance this device watches. Required for counters; left "
             "empty for devices that watch a zone or the checkout instead.")
    zone_id = fields.Many2one(
        "analitix.zone", string="Zone", index=True, ondelete="set null",
        domain="[('store_id', '=', store_id)]",
        help="Which internal zone this camera watches. Set for zone and "
             "checkout cameras; left empty for a door counter, which reports "
             "against its door instead.")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)

    role = fields.Selection(
        selection=[
            ("door_counter", "Door counter (in/out line)"),
            ("demographics", "Demographics (frontal camera)"),
            ("zone", "Zone camera"),
            ("checkout", "Checkout camera"),
            ("other", "Other"),
        ],
        string="Role", default="door_counter", required=True, tracking=True,
        help="What this device is for. Later phases route zone dwell, "
             "demographics and purchase attribution by role.")
    kind = fields.Selection(
        selection=[
            ("depth_cam", "Depth camera + edge PC (Orbbec / RealSense)"),
            ("diy_cv", "DIY edge (YOLO + ByteTrack)"),
            ("cctv_hik", "CCTV — Hikvision (ISAPI people counting)"),
            ("cctv_dahua", "CCTV — Dahua"),
            ("ir_beam", "IR beam counter"),
            ("other", "Other"),
        ],
        string="Hardware", default="depth_cam", required=True)
    critical = fields.Boolean(
        string="Critical", default=True, tracking=True,
        help="A critical device is one whose silence makes this store's numbers "
             "wrong: any door counter, or the checkout camera. When it goes "
             "offline the technical contacts are alerted. Clear the flag for a "
             "spare or experimental unit so it does not page anyone at 3 a.m.")

    # ------------------------------------------------------------------
    # Credentials
    # ------------------------------------------------------------------
    api_key_hash = fields.Char(
        string="API Key Hash", copy=False, index=True, readonly=True,
        groups="base.group_system",
        help="SHA-256 of the device key. The key itself is never stored.")
    api_key_hint = fields.Char(
        string="API Key", copy=False, readonly=True,
        help="Last characters of the active key, so a technician can tell which "
             "credential a device is carrying without being able to use it.")
    api_key_generated_at = fields.Datetime(
        string="Key Issued On", readonly=True, copy=False)
    api_key_revoked = fields.Boolean(
        string="Key Revoked", default=False, readonly=True, copy=False,
        tracking=True,
        help="A revoked device is refused by the ingest endpoint immediately, "
             "without waiting for anyone to reach the hardware.")

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    status = fields.Selection(
        selection=[
            ("never_seen", "Never seen"),
            ("online", "Online"),
            ("degraded", "Late"),
            ("offline", "Offline"),
            ("disabled", "Disabled"),
        ],
        string="Status", default="never_seen", readonly=True, copy=False,
        index=True, tracking=True)
    last_heartbeat = fields.Datetime(
        string="Last Heartbeat", readonly=True, copy=False, index=True)
    last_event_at = fields.Datetime(
        string="Last Event", readonly=True, copy=False)
    offline_since = fields.Datetime(
        string="Offline Since", readonly=True, copy=False)
    blind_since = fields.Datetime(
        string="Seeing Nothing Since", readonly=True, copy=False,
        help="Set when the device is heartbeating perfectly and has not "
             "reported a single crossing for far longer than it normally goes "
             "quiet. The agent is alive; the camera is not seeing.")
    agent_version = fields.Char(string="Agent Version", readonly=True, copy=False)
    edge_queue_size = fields.Integer(
        string="Edge Backlog", readonly=True, copy=False,
        help="Events still queued on the device itself, reported in its "
             "heartbeat. A backlog that keeps growing means the store's link "
             "is down or Odoo is refusing the data — the count is not lost yet, "
             "but it will be if the buffer overflows.")

    # ------------------------------------------------------------------
    # Ingest statistics / anomaly baseline (task 984, point 7)
    # ------------------------------------------------------------------
    event_count = fields.Integer(compute="_compute_event_count", string="Events")
    events_last_hour = fields.Integer(
        compute="_compute_event_rate", compute_sudo=True, string="Events / Hour")
    baseline_hourly_events = fields.Float(
        string="Normal Events / Hour", readonly=True, copy=False,
        help="Rolling average of this device's hourly volume, learned from its "
             "own history. Used to notice that a device suddenly reports ten "
             "times its usual traffic — a fault or a tampered agent.")
    anomaly_factor = fields.Float(
        string="Anomaly Factor", default=5.0, required=True,
        help="How far from its own baseline a device may drift before it is "
             "flagged. 5.0 means 'five times the usual hourly volume'.")

    note = fields.Text(string="Notes")
    config_json = fields.Text(
        string="Edge Configuration",
        help="Free-form JSON handed to the agent by the config endpoint: line "
             "coordinates, camera index, zone polygons. Kept here so an "
             "implementer can retune a camera from Odoo instead of going back "
             "to the store with a laptop.")

    _device_uid_uniq = models.Constraint(
        "unique(device_uid)", "This Device UID is already in use.")
    _api_key_hash_uniq = models.Constraint(
        "unique(api_key_hash)",
        "This API key is already assigned to another device.")

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        devices = super().create(vals_list)
        for device in devices:
            if not device.sudo().api_key_hash:
                device._issue_key()
        return devices

    @api.constrains("door_id", "zone_id", "store_id")
    def _check_door_store(self):
        for device in self:
            if device.door_id and device.door_id.store_id != device.store_id:
                raise UserError(_(
                    "Device '%(dev)s' points at a door of another store. A "
                    "device belongs to exactly one store.", dev=device.name))
            if device.zone_id and device.zone_id.store_id != device.store_id:
                raise UserError(_(
                    "Device '%(dev)s' points at a zone of another store.",
                    dev=device.name))

    @api.onchange("store_id")
    def _onchange_store_clear_door(self):
        if self.door_id and self.door_id.store_id != self.store_id:
            self.door_id = False

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------
    def _issue_key(self):
        """Mint a key, store only its digest, and return the plaintext once."""
        self.ensure_one()
        raw = "%s_%s" % (KEY_PREFIX, secrets.token_urlsafe(32))
        self.sudo().write({
            "api_key_hash": hash_key(raw),
            "api_key_hint": "…%s" % raw[-6:],
            "api_key_generated_at": fields.Datetime.now(),
            "api_key_revoked": False,
        })
        return raw

    def action_rotate_key(self):
        """Issue a fresh key and show it once — it cannot be retrieved later."""
        self.ensure_one()
        raw = self._issue_key()
        self.message_post(body=_(
            "API key rotated by %s. The previous key stopped working "
            "immediately.", self.env.user.display_name))
        self.env["analitix.audit.log"].sudo().log(
            action="key_rotate", model=self._name, res_id=self.id,
            store=self.store_id, note=_("Key rotated for device %s", self.device_uid))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("New API key — copy it now"),
                "message": _(
                    "%(key)s\n\nThis is the only time it is shown. Odoo stores "
                    "only a hash of it; if it is lost, rotate again.",
                    key=raw),
                "type": "warning",
                "sticky": True,
            },
        }

    def action_revoke_key(self):
        """Cut this device off at once, without touching the hardware."""
        for device in self:
            device.sudo().write({
                "api_key_revoked": True,
                "status": "disabled",
            })
            device.message_post(body=_(
                "API key REVOKED by %s. This device can no longer send data.",
                self.env.user.display_name))
            self.env["analitix.audit.log"].sudo().log(
                action="key_revoke", model=self._name, res_id=device.id,
                store=device.store_id,
                note=_("Key revoked for device %s", device.device_uid))
        return True

    @api.model
    def _authenticate(self, raw_key):
        """Resolve a bearer key to its device, or an empty recordset.

        Looks up by digest, so the key never has to be compared in the clear
        and the lookup rides the index on ``api_key_hash``.
        """
        if not raw_key:
            return self.browse()
        return self.sudo().search([
            ("api_key_hash", "=", hash_key(raw_key)),
            ("api_key_revoked", "=", False),
            ("active", "=", True),
        ], limit=1)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    def _mark_seen(self, agent_version=None, queue_size=None):
        """Record a sign of life. Called on heartbeat and on ingest."""
        now = fields.Datetime.now()
        vals = {"last_heartbeat": now, "status": "online", "offline_since": False}
        if agent_version:
            vals["agent_version"] = agent_version
        if queue_size is not None:
            vals["edge_queue_size"] = queue_size
        for device in self:
            recovered = device.status in ("offline", "degraded")
            device.sudo().write(vals)
            if recovered:
                device.message_post(body=_("Device back online."))

    @api.model
    def _cron_check_health(self):
        """Flag devices that stopped reporting, and alert on the critical ones.

        Runs on a cron because absence of data is not an event: nothing will
        arrive to tell us a camera died, which is precisely the failure the
        customer is paying us to notice.
        """
        now = fields.Datetime.now()
        devices = self.sudo().search([
            ("active", "=", True),
            ("api_key_revoked", "=", False),
        ])
        newly_down = self.browse()
        newly_blind = self.browse()
        for device in devices:
            store = device.store_id
            if not store.capture_enabled:
                # Paused on purpose: silence here is expected, not a fault.
                if device.status != "disabled":
                    device.write({"status": "disabled"})
                continue
            if not device.last_heartbeat:
                if device.status != "never_seen":
                    device.write({"status": "never_seen"})
                continue
            silent_min = (now - device.last_heartbeat).total_seconds() / 60.0
            if silent_min >= store.offline_threshold_min:
                if device.status != "offline":
                    device.write({"status": "offline", "offline_since": now})
                    device.message_post(body=_(
                        "Device OFFLINE — no heartbeat for %(min)s minutes "
                        "(threshold %(limit)s).",
                        min=int(silent_min), limit=store.offline_threshold_min))
                    if device.critical:
                        newly_down |= device
            elif silent_min >= store.degraded_threshold_min:
                if device.status not in ("degraded", "offline"):
                    device.write({"status": "degraded"})
            elif device.status != "online":
                device.write({"status": "online", "offline_since": False})

            if device.status == "online" and device._check_blind(now):
                if device.critical:
                    newly_blind |= device
        for device in newly_down:
            device._raise_offline_alert()
        for device in newly_blind:
            device._raise_blind_alert()
        return True

    def _check_blind(self, now):
        """A device that heartbeats perfectly and sees nothing at all.

        This is the failure the rest of the health check cannot see, and it is
        worse than an offline camera precisely because it looks fine: the agent
        is up, the heartbeat is punctual, the dashboard is green, and the shop
        simply stops being counted. A weekend can pass before anybody notices,
        and the numbers for those days are quietly wrong rather than visibly
        missing.

        Measured against the device's **own** recent normal, never against a
        clock. A shop is shut at four in the morning and a counter that reports
        nothing then is working correctly; the same silence at two in the
        afternoon is not. The baseline the anomaly cron already maintains is
        exactly the right yardstick, and a device without enough history to have
        one is left alone rather than guessed at.

        Returns True only on the transition, so the alert fires once.
        """
        self.ensure_one()
        store = self.store_id
        expected = self.baseline_hourly_events or 0.0
        if expected < MIN_BLIND_BASELINE:
            # Too quiet to judge. A service door that sees four people a day
            # would trip this every lunchtime.
            return False

        window = max(store.blind_after_minutes, 1)
        since = now - timedelta(minutes=window)
        if self.last_event_at and self.last_event_at >= since:
            if self.blind_since:
                self.write({"blind_since": False})
                self.message_post(body=_(
                    "Seeing again — crossings are arriving from this device."))
            return False

        # Nothing seen for the whole window, and its own history says there
        # should have been roughly %s.
        if self.blind_since:
            return False          # already flagged; do not alert again
        self.write({"blind_since": now})
        self.message_post(body=_(
            "Device is HEARTBEATING BUT SEEING NOTHING — no crossing for "
            "%(min)s minutes, against a usual %(rate).1f an hour. The agent is "
            "alive, so this is not an outage: check the camera, the lens and "
            "the virtual line. This store's numbers are wrong rather than "
            "missing while it lasts.",
            min=window, rate=expected))
        return True

    def _raise_blind_alert(self):
        """Tell a human. Deliberately worded apart from an offline device: the
        two look nothing alike to whoever has to fix them."""
        self.ensure_one()
        store = self.store_id
        responsible = store.alert_user_id or self.create_uid
        try:
            self.activity_schedule(
                "mail.mail_activity_data_warning",
                summary=_("Analitix: camera alive but seeing nothing"),
                note=_(
                    "Device <b>%(dev)s</b> of store <b>%(store)s</b> is "
                    "reporting in normally and has not counted a single person "
                    "for %(min)s minutes. Its own history says it should be "
                    "seeing about %(rate).1f an hour.<br/><br/>"
                    "Nothing is offline, so nothing else will flag this. Look "
                    "at the camera itself: a lens that was knocked, a view that "
                    "something now blocks, or a virtual line that no longer "
                    "sits across the doorway.<br/><br/>"
                    "<b>While it lasts, this store's figures are wrong rather "
                    "than missing</b> — the conversion rate reads high because "
                    "the tickets keep arriving and the visitors do not.",
                    dev=self.name, store=store.name,
                    min=store.blind_after_minutes,
                    rate=self.baseline_hourly_events or 0.0),
                user_id=responsible.id)
        except ValueError:
            _logger.warning(
                "Analitix: could not schedule a blind-device activity for %s",
                self.id)
        self.env["analitix.audit.log"].sudo().log(
            action="anomaly", model=self._name, res_id=self.id, store=store,
            note=_("Device %s heartbeating but reporting no crossings",
                   self.name))
        return True

    def _raise_offline_alert(self):
        """Tell a human that a critical device is dark: activity + e-mail."""
        self.ensure_one()
        store = self.store_id
        responsible = store.alert_user_id or self.create_uid
        try:
            self.activity_schedule(
                "mail.mail_activity_data_warning",
                summary=_("Analitix: critical device offline"),
                note=_(
                    "Device <b>%(dev)s</b> of store <b>%(store)s</b> stopped "
                    "reporting. While it is down, this store's visitor count "
                    "and conversion are incomplete.",
                    dev=self.name, store=store.name),
                user_id=responsible.id)
        except ValueError:
            _logger.warning(
                "Analitix: could not schedule an activity for device %s", self.id)
        template = self.env.ref(
            "analitix.mail_template_device_offline", raise_if_not_found=False)
        if template and store.alert_partner_ids:
            template.with_context(
                alert_partner_ids=store.alert_partner_ids.ids
            ).send_mail(self.id, force_send=False)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    def _compute_event_count(self):
        data = self.env["analitix.event"]._read_group(
            [("device_id", "in", self.ids)],
            groupby=["device_id"], aggregates=["__count"])
        mapped = {device.id: count for device, count in data}
        for device in self:
            device.event_count = mapped.get(device.id, 0)

    def _compute_event_rate(self):
        since = fields.Datetime.now() - timedelta(hours=1)
        data = self.env["analitix.event"]._read_group(
            [("device_id", "in", self.ids), ("event_time", ">=", since)],
            groupby=["device_id"], aggregates=["__count"])
        mapped = {device.id: count for device, count in data}
        for device in self:
            device.events_last_hour = mapped.get(device.id, 0)

    @api.model
    def _cron_update_baselines(self):
        """Refresh each device's 'normal' hourly volume and flag outliers.

        Security lens rather than business lens (task 984, point 7): a camera
        that suddenly triples its output has either broken or been tampered
        with, and either way the numbers it is feeding the customer's dashboard
        should not be trusted silently.
        """
        now = fields.Datetime.now()
        week_ago = now - timedelta(days=7)
        hour_ago = now - timedelta(hours=1)
        devices = self.sudo().search([("active", "=", True)])
        if not devices:
            return True
        weekly = dict(self.env["analitix.event"]._read_group(
            [("device_id", "in", devices.ids), ("event_time", ">=", week_ago),
             ("event_time", "<", hour_ago)],
            groupby=["device_id"], aggregates=["__count"]))
        recent = dict(self.env["analitix.event"]._read_group(
            [("device_id", "in", devices.ids), ("event_time", ">=", hour_ago)],
            groupby=["device_id"], aggregates=["__count"]))
        for device in devices:
            # 7 days minus the last hour ≈ 167 hours of history
            history = weekly.get(device, 0) or 0
            baseline = history / 167.0
            device.write({"baseline_hourly_events": baseline})
            last_hour = recent.get(device, 0) or 0
            # Two guards, and both earn their place:
            #
            # * enough history to *have* a normal — a camera installed
            #   yesterday looks anomalous against everything;
            # * an absolute floor as well as the ratio — a quiet store with a
            #   baseline of 0.2 events/hour would otherwise page the technician
            #   over a family of four walking in together.
            if history >= MIN_HISTORY_EVENTS and last_hour > max(
                    baseline * device.anomaly_factor, MIN_ANOMALY_EVENTS):
                device.message_post(body=_(
                    "Ingest anomaly: %(count)s events in the last hour against "
                    "a usual %(base).1f. Check the device for a fault or "
                    "tampering — its data is suspect until reviewed.",
                    count=last_hour, base=baseline))
                self.env["analitix.audit.log"].sudo().log(
                    action="anomaly", model=self._name, res_id=device.id,
                    store=device.store_id,
                    note=_("Volume anomaly: %(c)s vs baseline %(b).1f/h",
                           c=last_hour, b=baseline))
        return True

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def action_view_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Crossing Events"),
            "res_model": "analitix.event",
            "view_mode": "list,graph,pivot,form",
            "domain": [("device_id", "=", self.id)],
            "context": {"default_device_id": self.id},
        }
