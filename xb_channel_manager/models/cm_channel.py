# -*- coding: utf-8 -*-
import logging
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CmChannel(models.Model):
    _name = "xb.cm.channel"
    _description = "OTA Channel Connection"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, id"

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True,
        default=lambda self: self.env.company)
    channel_type = fields.Selection([
        ("ical", "iCal (Airbnb / Booking.com / Vrbo calendars)"),
        ("channex", "Channex API (Booking.com, Expedia, Airbnb…)"),
    ], required=True, default="ical", tracking=True)
    ota_name = fields.Selection([
        ("airbnb", "Airbnb"),
        ("booking", "Booking.com"),
        ("expedia", "Expedia"),
        ("vrbo", "Vrbo"),
        ("other", "Other"),
    ], string="Platform", default="airbnb",
        help="Informative: which OTA this connection belongs to.")
    state = fields.Selection([
        ("draft", "Draft"),
        ("connected", "Connected"),
        ("error", "Error"),
        ("paused", "Paused"),
    ], default="draft", tracking=True)

    listing_ids = fields.One2many("xb.cm.listing", "channel_id")
    listing_count = fields.Integer(compute="_compute_counts")
    reservation_ids = fields.One2many("xb.cm.reservation", "channel_id")
    reservation_count = fields.Integer(compute="_compute_counts")
    pending_count = fields.Integer(compute="_compute_counts")

    import_policy = fields.Selection([
        ("draft", "Create draft quotations (manual confirmation)"),
        ("confirm", "Confirm orders and block availability"),
    ], default="confirm", required=True, tracking=True,
        help="What to do with reservations imported from the channel.")
    auto_import = fields.Boolean(
        default=True,
        help="Import new reservations automatically on each sync. When "
             "disabled they stay in the inbox for manual review.")
    cancel_policy = fields.Selection([
        ("manual", "Flag for manual review"),
        ("auto", "Cancel the sale order automatically"),
    ], default="manual", required=True,
        help="What to do when a reservation disappears from the channel "
             "or a cancellation webhook arrives.")
    sync_interval = fields.Integer(
        string="Sync every (minutes)", default=30,
        help="Minimum minutes between automatic syncs of this channel.")
    last_sync = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)

    # --- Channex specific -------------------------------------------------
    channex_base_url = fields.Char(
        string="Channex base URL", default="https://staging.channex.io",
        help="https://staging.channex.io for the sandbox, "
             "https://app.channex.io for production.")
    channex_api_key = fields.Char(string="Channex API key")
    channex_property_id = fields.Char(string="Channex property ID")
    webhook_token = fields.Char(
        readonly=True, copy=False,
        default=lambda self: secrets.token_urlsafe(24))
    webhook_url = fields.Char(compute="_compute_webhook_url")

    export_horizon_days = fields.Integer(
        string="Export horizon (days)", default=365,
        help="How many days ahead of today to publish/push.")

    @api.depends("listing_ids", "reservation_ids",
                 "reservation_ids.state")
    def _compute_counts(self):
        for rec in self:
            rec.listing_count = len(rec.listing_ids)
            rec.reservation_count = len(rec.reservation_ids)
            rec.pending_count = len(rec.reservation_ids.filtered(
                lambda r: r.state in ("new", "conflict", "error")))

    def _compute_webhook_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url") or ""
        for rec in self:
            rec.webhook_url = (
                "%s/cm/channex/webhook/%s" % (base, rec.webhook_token)
                if rec.channel_type == "channex" else False)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_connect(self):
        for rec in self:
            if rec.channel_type == "channex":
                rec._channex_test_connection()
            rec.state = "connected"
        return True

    def action_pause(self):
        self.write({"state": "paused"})

    def action_sync_now(self):
        self.ensure_one()
        self.with_context(cm_force_sync=True)._sync()
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {"type": "success", "sticky": False,
                       "message": _("Synchronization finished.")},
        }

    def action_view_reservations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reservations"),
            "res_model": "xb.cm.reservation",
            "view_mode": "list,form",
            "domain": [("channel_id", "=", self.id)],
            "context": {"default_channel_id": self.id},
        }

    def action_view_listings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Room mappings"),
            "res_model": "xb.cm.listing",
            "view_mode": "list,form",
            "domain": [("channel_id", "=", self.id)],
            "context": {"default_channel_id": self.id},
        }

    def action_regenerate_webhook_token(self):
        for rec in self:
            rec.webhook_token = secrets.token_urlsafe(24)

    # ------------------------------------------------------------------
    # Sync dispatch
    # ------------------------------------------------------------------
    def _sync(self):
        """Run one sync cycle of this channel (driver dispatch)."""
        for rec in self:
            if rec.state not in ("connected",) and not self.env.context.get(
                    "cm_force_sync"):
                continue
            try:
                if rec.channel_type == "ical":
                    rec._sync_ical()
                elif rec.channel_type == "channex":
                    rec._sync_channex()
                rec.write({"last_sync": fields.Datetime.now(),
                           "last_error": False})
                if rec.state == "error":
                    rec.state = "connected"
            except Exception as exc:  # noqa: BLE001 — cron must survive
                _logger.exception("CM sync failed for channel %s", rec.name)
                rec.write({"state": "error", "last_error": str(exc)})
                self.env["xb.cm.log"].sudo().log(
                    rec, "error", "sync", str(exc))

    def _sync_ical(self):
        self.ensure_one()
        for listing in self.listing_ids.filtered("active"):
            listing._ical_pull()

    def _sync_channex(self):
        self.ensure_one()
        client = self._channex_client()
        # 1) pull new/changed bookings through the feed (with ack)
        self.env["xb.cm.reservation"]._channex_pull_feed(self, client)
        # 2) push availability & rates
        for listing in self.listing_ids.filtered("active"):
            listing._channex_push_ari(client)

    def _channex_client(self):
        self.ensure_one()
        if not (self.channex_api_key and self.channex_property_id):
            raise UserError(_(
                "Set the Channex API key and property ID first."))
        from .channex_client import ChannexClient
        return ChannexClient(self.channex_base_url, self.channex_api_key)

    def _channex_test_connection(self):
        self.ensure_one()
        client = self._channex_client()
        props = client.get("/api/v1/properties")
        ids = [p.get("id") for p in props.get("data", [])]
        if self.channex_property_id not in ids:
            raise UserError(_(
                "Connected to Channex, but property %s was not found in "
                "the account (found: %s).",
                self.channex_property_id, ", ".join(ids) or "-"))
        self.env["xb.cm.log"].sudo().log(
            self, "info", "connect", "Channex connection OK")

    # ------------------------------------------------------------------
    # Cron entry point
    # ------------------------------------------------------------------
    @api.model
    def _cron_sync_all(self):
        now = fields.Datetime.now()
        channels = self.search([("state", "=", "connected")])
        for channel in channels:
            due = (not channel.last_sync or channel.last_sync
                   + timedelta(minutes=channel.sync_interval or 30) <= now)
            if due:
                channel._sync()
                # each channel commits its own progress; a failure in one
                # channel must not roll back the others
                self.env.cr.commit()  # pylint: disable=invalid-commit
