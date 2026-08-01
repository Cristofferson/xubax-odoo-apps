# -*- coding: utf-8 -*-
"""Lost sales — where the customer sees the money leaving.

This is the number that sells the product. Not "you had 400 visitors" but
"eleven people stood at the ring counter for over three minutes yesterday,
nobody spoke to nine of them, and none of those nine bought anything."

What counts as a lost sale here
-------------------------------
Someone who lingered past the zone's threshold, was **not** served, and left
**without** a matching ticket. All three conditions, because each one on its own
is ordinary:

* long dwell alone is a browser, and browsers are not a problem;
* unserved alone might be a customer who wanted to be left alone;
* no ticket alone is most of any shop's traffic.

Together they are a specific, actionable event: somebody was interested enough
to stand there, nobody helped them, and they left.

It is deliberately conservative. A false lost sale costs a salesperson a trip
and, repeated, their trust in the whole system — after which no alert works.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models, _

from .analitix_job import register_handler

_logger = logging.getLogger(__name__)


class AnalitixLostSale(models.Model):
    _name = "analitix.lost.sale"
    _description = "Analitix Lost Sale"
    _order = "detected_at desc, id desc"
    _rec_name = "display_name"

    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)
    zone_id = fields.Many2one(
        "analitix.zone", string="Zone", index=True, ondelete="set null")
    visitor_id = fields.Many2one(
        "analitix.visitor", string="Visit", index=True, ondelete="cascade")
    dwell_id = fields.Many2one(
        "analitix.zone.dwell", string="Dwell", ondelete="set null")

    detected_at = fields.Datetime(
        string="Detected", required=True, index=True,
        default=lambda self: fields.Datetime.now())
    dwell_seconds = fields.Integer(string="Dwell (s)")
    was_served = fields.Boolean(
        string="Was Served",
        help="A salesperson did attend them and they still left. Kept, because "
             "'we attend them and they leave anyway' is a different and more "
             "expensive problem than 'nobody goes over'.")

    state = fields.Selection(
        selection=[
            ("open", "Open"),
            ("rescued", "Rescued"),
            ("lost", "Lost"),
        ],
        string="Status", default="open", required=True, index=True,
        help="Rescued means this visit produced a ticket after the alert. It is "
             "the figure the monthly value report is built on.")
    alert_id = fields.Many2one(
        "analitix.alert", string="Alert", ondelete="set null")
    lead_id = fields.Many2one(
        "crm.lead", string="Lead", ondelete="set null",
        help="Optional CRM follow-up. Only created for an identified customer — "
             "a lead with no way to contact anybody is filing clutter.")
    pos_order_id = fields.Many2one(
        "pos.order", string="Rescued By", ondelete="set null")
    estimated_value = fields.Monetary(
        string="Estimated Value", currency_field="currency_id",
        help="The store's average ticket at the time. An estimate, and labelled "
             "as one: the real value of a sale that never happened cannot be "
             "known, and quoting it to the cent would be dishonest.")
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True)

    _store_detected_idx = models.Index("(store_id, detected_at DESC)")

    @api.depends("zone_id", "detected_at")
    def _compute_display_name(self):
        for record in self:
            record.display_name = _(
                "%(zone)s · %(when)s",
                zone=record.zone_id.name or _("store"),
                when=fields.Datetime.to_string(record.detected_at))

    # ------------------------------------------------------------------
    @api.model
    def _evaluate_dwell(self, dwell):
        """Decide whether one dwell is worth a nudge, and send it if so."""
        zone = dwell.zone_id
        store = dwell.store_id
        if not store.lost_sale_enabled or not zone.alert_on_dwell:
            return self.browse()
        if dwell.seconds < zone.lost_sale_seconds or dwell.served:
            return self.browse()
        if self.sudo().search_count([("dwell_id", "=", dwell.id)]):
            return self.browse()   # already raised for this dwell

        alert = self.env["analitix.alert"].raise_alert(
            store, "lost_sale",
            _("%(zone)s: customer unattended for %(mins)s min",
              zone=zone.name, mins=int(dwell.seconds / 60)),
            body=_("Someone has been at %(zone)s for %(mins)s minutes and "
                   "nobody has been over. Worth a look.",
                   zone=zone.name, mins=int(dwell.seconds / 60)),
            zone=zone, visitor=dwell.visitor_id)

        record = self.sudo().create({
            "store_id": store.id,
            "zone_id": zone.id,
            "visitor_id": dwell.visitor_id.id,
            "dwell_id": dwell.id,
            "detected_at": fields.Datetime.now(),
            "dwell_seconds": dwell.seconds,
            "was_served": dwell.served,
            "alert_id": alert.id if alert else False,
            "estimated_value": store._average_ticket(),
        })
        dwell.sudo().alert_id = alert.id if alert else False
        return record

    # ------------------------------------------------------------------
    @api.model
    def _run_settle(self, job):
        """Close out lost sales once the visit is over.

        Runs behind the visit rather than at the moment of the alert, because
        at that moment nobody knows the answer yet: the whole question is
        whether the nudge worked, and that is only visible after they either
        bought or left.
        """
        records = self.sudo().browse(job._payload().get("ids") or []).exists()
        for record in records:
            record._settle()
        return True

    def _settle(self):
        self.ensure_one()
        if self.state != "open":
            return
        match = self.env["analitix.sale.match"].sudo().search([
            ("visitor_id", "=", self.visitor_id.id)], limit=1)
        if match:
            self.write({
                "state": "rescued",
                "pos_order_id": match.pos_order_id.id,
            })
            if self.alert_id:
                self.alert_id.sudo().outcome = "sold"
            return
        if self.visitor_id.state == "left":
            self.write({"state": "lost"})
            self._maybe_create_lead()

    def _maybe_create_lead(self):
        """A CRM lead, but only when there is somebody to follow up with."""
        self.ensure_one()
        store = self.store_id
        if not store.lost_sale_create_lead or self.lead_id:
            return
        partner = self.visitor_id.signature_id.partner_id
        if not partner:
            # Anonymous: nothing to contact. A lead with no name and no phone
            # is filing clutter that makes the real ones harder to find.
            return
        self.sudo().lead_id = self.env["crm.lead"].sudo().create({
            "name": _("Unattended at %(zone)s — %(store)s",
                      zone=self.zone_id.name or _("store"), store=store.name),
            "partner_id": partner.id,
            "company_id": store.company_id.id,
            "description": _(
                "Analitix saw this customer spend %(mins)s minutes at "
                "%(zone)s on %(when)s without being served, and leave without "
                "buying.",
                mins=int(self.dwell_seconds / 60),
                zone=self.zone_id.name or _("the store"),
                when=fields.Datetime.to_string(self.detected_at)),
        }).id

    @api.model
    def _cron_settle_open(self):
        """Sweep up anything the per-visit job missed."""
        cutoff = fields.Datetime.now() - timedelta(hours=4)
        stale = self.sudo().search([
            ("state", "=", "open"), ("detected_at", "<", cutoff)], limit=2000)
        for record in stale:
            record._settle()
            if record.state == "open":
                # The visit never closed either; call it lost rather than
                # leaving it open forever and quietly deflating the report.
                record.write({"state": "lost"})
        return True


register_handler("lost_sale_settle", "analitix.lost.sale", "_run_settle")
