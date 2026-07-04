# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models


class CmLog(models.Model):
    _name = "xb.cm.log"
    _description = "Channel Manager Log"
    _order = "id desc"

    channel_id = fields.Many2one(
        "xb.cm.channel", required=True, ondelete="cascade", index=True)
    listing_id = fields.Many2one(
        "xb.cm.listing", ondelete="set null")
    level = fields.Selection([
        ("info", "Info"),
        ("warning", "Warning"),
        ("error", "Error"),
    ], default="info", required=True, index=True)
    kind = fields.Selection([
        ("sync", "Sync"),
        ("connect", "Connection"),
        ("ical_export", "iCal export"),
        ("ical_import", "iCal import"),
        ("ari_push", "Availability/rate push"),
        ("webhook", "Webhook"),
        ("booking", "Booking"),
    ], default="sync", required=True)
    message = fields.Text()

    @api.model
    def log(self, channel, level, kind, message, listing=None):
        return self.create({
            "channel_id": channel.id,
            "listing_id": listing.id if listing else False,
            "level": level,
            "kind": kind,
            "message": message,
        })

    @api.model
    def _cron_vacuum(self, days=30):
        self.search([
            ("create_date", "<",
             fields.Datetime.now() - timedelta(days=days)),
        ]).unlink()
