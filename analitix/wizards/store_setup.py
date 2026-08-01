# -*- coding: utf-8 -*-
"""Onboarding a new customer store, in one screen.

This wizard is the answer to the master instruction's central demand: the
product is sold to many different stores, so *how many doors this one has* is
something an implementer types in, never something a developer edits.  It takes
a name, a floor area, which POS registers to compare against, and a list of
doors — one row, two rows, seven rows — and produces the store, its doors, one
counting device per door, and their API keys.

The keys are shown once, at the end, because that is the only moment they
exist: Odoo keeps only their hashes (see ``analitix.device``).  The final screen
is therefore the thing the implementer copies into each mini-PC before leaving
the site, and it says so.
"""
import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AnalitixStoreSetup(models.TransientModel):
    _name = "analitix.store.setup"
    _description = "Analitix — New Store Setup"

    name = fields.Char(string="Store Name", required=True)
    code = fields.Char(
        string="Reference",
        help="Short code, e.g. 'MOR-01'. Device UIDs are derived from it.")
    company_id = fields.Many2one(
        "res.company", string="Company", required=True,
        default=lambda self: self.env.company)
    tz = fields.Selection(
        selection=lambda self: [(t, t) for t in pytz.all_timezones],
        string="Timezone", default=lambda self: self.env.user.tz or "UTC",
        required=True)
    area_sqm = fields.Float(string="Total m²")
    sales_area_sqm = fields.Float(string="Sales-floor m²")

    match_mode = fields.Selection(
        selection=[
            ("registers", "Specific POS registers"),
            ("company", "Whole company"),
        ],
        string="Match sales by", required=True, default="registers")
    register_ids = fields.Many2many("pos.config", string="POS Registers")

    door_ids = fields.One2many(
        "analitix.store.setup.door", "wizard_id", string="Doors")

    heartbeat_interval_s = fields.Integer(string="Heartbeat Interval (s)", default=60)
    offline_threshold_min = fields.Integer(string="Offline After (min)", default=5)
    alert_partner_ids = fields.Many2many(
        "res.partner", string="Technical Contacts")

    state = fields.Selection(
        selection=[("draft", "Setup"), ("done", "Credentials")],
        default="draft")
    store_id = fields.Many2one("analitix.store", readonly=True)
    credentials = fields.Text(string="Device Credentials", readonly=True)

    @api.model
    def default_get(self, fields_list):
        """Open with one door already filled in.

        Most stores have exactly one, so the common case should need no typing;
        adding the second and third is one click each. Starting from an empty
        list would suggest zero doors is a sensible configuration, and it is not.
        """
        values = super().default_get(fields_list)
        if "door_ids" in fields_list and not values.get("door_ids"):
            values["door_ids"] = [(0, 0, {
                "name": _("Main Entrance"), "code": "M", "kind": "main",
            })]
        return values

    def action_create_store(self):
        self.ensure_one()
        if not self.door_ids:
            raise UserError(_(
                "Add at least one door. A store with no entrance has nothing "
                "to count."))
        if self.match_mode == "registers" and not self.register_ids:
            raise UserError(_(
                "Pick the POS registers whose tickets belong to this store, or "
                "switch to 'Whole company'. Without either, conversion has no "
                "sales side and every hour will read 0%."))

        store = self.env["analitix.store"].create({
            "name": self.name,
            "code": self.code,
            "company_id": self.company_id.id,
            "tz": self.tz,
            "area_sqm": self.area_sqm,
            "sales_area_sqm": self.sales_area_sqm,
            "match_mode": self.match_mode,
            "register_ids": [(6, 0, self.register_ids.ids)],
            "heartbeat_interval_s": self.heartbeat_interval_s,
            "offline_threshold_min": self.offline_threshold_min,
            "alert_partner_ids": [(6, 0, self.alert_partner_ids.ids)],
            "alert_user_id": self.env.user.id,
        })

        lines = []
        for sequence, row in enumerate(self.door_ids, start=1):
            door = self.env["analitix.door"].create({
                "store_id": store.id,
                "name": row.name,
                "code": row.code,
                "kind": row.kind,
                "counts_visitors": row.counts_visitors,
                "sequence": sequence * 10,
            })
            if not row.create_device:
                continue
            # Never name a local variable `uid` in a method that calls _().
            # Odoo's translation machinery guesses the language by inspecting
            # the calling frame for a local called `uid` and treating it as a
            # res.users id — a string here makes it query res_users with the
            # characters of the device UID and blow up somewhere unrelated.
            device_uid = row.device_uid or self._suggest_uid(store, door)
            device = self.env["analitix.device"].create({
                "name": _("%s counter", door.name),
                "device_uid": device_uid,
                "store_id": store.id,
                "door_id": door.id,
                "role": "door_counter",
                "kind": row.hardware,
                "critical": True,
            })
            # _issue_key returns the plaintext exactly once, at creation.
            raw_key = device._issue_key()
            lines.append(_(
                "Door: %(door)s\n"
                "  Device UID : %(uid)s\n"
                "  API key    : %(key)s\n",
                door=door.name, uid=device.device_uid, key=raw_key))

        self.write({
            "state": "done",
            "store_id": store.id,
            "credentials": "\n".join(lines) if lines else _(
                "No devices were created. Add them from the store's Devices "
                "tab when the hardware is on site."),
        })
        store.message_post(body=_(
            "Store created by %(user)s with %(doors)s door(s).",
            user=self.env.user.display_name, doors=len(self.door_ids)))
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    @api.model
    def _suggest_uid(self, store, door):
        base = (store.code or store.name or "store").lower().replace(" ", "-")
        suffix = (door.code or door.name or "door").lower().replace(" ", "-")
        return "%s-%s-counter" % (base, suffix)

    def action_open_store(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "analitix.store",
            "res_id": self.store_id.id,
            "view_mode": "form",
        }


class AnalitixStoreSetupDoor(models.TransientModel):
    _name = "analitix.store.setup.door"
    _description = "Analitix — New Store Setup Door"
    _order = "id"

    wizard_id = fields.Many2one(
        "analitix.store.setup", required=True, ondelete="cascade")
    name = fields.Char(string="Door Name", required=True)
    code = fields.Char(string="Code")
    kind = fields.Selection(
        selection=[
            ("main", "Main entrance"),
            ("secondary", "Secondary entrance"),
            ("mall", "Mall / gallery entrance"),
            ("service", "Service / staff entrance"),
            ("emergency", "Emergency exit"),
        ],
        string="Type", default="main", required=True)
    counts_visitors = fields.Boolean(
        string="Counts Visitors", default=True,
        help="Clear this for a staff or service door: it stays measured, but "
             "its traffic stops distorting the conversion rate.")
    create_device = fields.Boolean(
        string="Create Device", default=True,
        help="Create the counting device and issue its API key now. Clear it "
             "for a door whose hardware is not installed yet.")
    device_uid = fields.Char(
        string="Device UID",
        help="Leave empty to derive it from the store and door codes.")
    hardware = fields.Selection(
        selection=[
            ("depth_cam", "Depth camera + edge PC"),
            ("diy_cv", "DIY edge (YOLO + ByteTrack)"),
            ("cctv_hik", "CCTV — Hikvision"),
            ("cctv_dahua", "CCTV — Dahua"),
            ("ir_beam", "IR beam counter"),
            ("other", "Other"),
        ],
        string="Hardware", default="depth_cam", required=True)

    @api.onchange("kind")
    def _onchange_kind(self):
        """A service or emergency door defaults to not counting customers.

        Overridable — some stores really do have customers coming through the
        service door — but the default should match what is true most of the
        time, so nobody has to remember it.
        """
        if self.kind in ("service", "emergency"):
            self.counts_visitors = False
