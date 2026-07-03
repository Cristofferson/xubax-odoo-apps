# -*- coding: utf-8 -*-
from datetime import timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FootfallStore(models.Model):
    """A physical store: the real unit of footfall analysis.

    A store aggregates one or more ENTRANCES (counting devices — their visitors
    are summed) and the POS sales it should be compared against. Sales are
    matched either by a set of POS registers (when several registers live in the
    same shop) or by the whole company (single-store company).

    This makes the conversion KPI correct regardless of layout:
      * several registers in one store  -> tickets summed across them,
      * several doors in one store       -> visitors summed across them.
    """
    _name = "xb.footfall.store"
    _description = "Footfall Store"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", string="Company", required=True,
        default=lambda self: self.env.company)
    match_mode = fields.Selection(
        selection=[
            ("registers", "Specific POS registers"),
            ("company", "Whole company"),
        ],
        string="Match sales by", required=True, default="registers",
        help="How POS sales are attributed to this store for conversion:\n"
             "• Specific POS registers: only orders from the registers below "
             "(use when several stores share one company).\n"
             "• Whole company: all POS orders of the company (use when the "
             "company has a single store).")
    register_ids = fields.Many2many(
        "pos.config", relation="xbf_store_register_rel",
        column1="store_id", column2="config_id",
        string="POS Registers",
        help="Registers whose tickets count toward this store's conversion. "
             "Only used when 'Match sales by' is 'Specific POS registers'.")
    device_ids = fields.One2many(
        "xb.footfall.device", "store_id", string="Devices")
    device_count = fields.Integer(compute="_compute_counts")
    register_count = fields.Integer(compute="_compute_counts")
    area_sqm = fields.Float(
        string="Total m²",
        help="Total floor area of the store in square meters. Enables the "
             "sales-density KPIs (revenue and visitors per m²).")
    sales_area_sqm = fields.Float(
        string="Sales-floor m²",
        help="Selling area in square meters (excludes storage/offices). "
             "Optional; use it when you want density over the sellable floor "
             "only rather than the whole premises.")
    note = fields.Text(string="Notes")
    # --- Occupancy over the selected period (default: today, live) ---
    # The window comes from the search context key 'ff_period' so the same
    # cards can show the live count (default) or a chosen historical period
    # (yesterday / this week / this month) via Odoo's native filters.
    visitors_in = fields.Integer(
        string="Visitors In", compute="_compute_live", compute_sudo=True,
        help="People who entered the store during the selected period "
             "(default: today, in your timezone).")
    visitors_out = fields.Integer(
        string="Visitors Out", compute="_compute_live", compute_sudo=True,
        help="People who left the store during the selected period.")
    live_occupancy = fields.Integer(
        string="Occupancy", compute="_compute_live", compute_sudo=True,
        help="Entrances minus exits over the selected period (never negative). "
             "For the default 'today' period this is a live estimate of the "
             "people currently inside, reset every midnight.")
    last_event_time = fields.Datetime(
        string="Last Event", compute="_compute_live", compute_sudo=True,
        help="Time of the most recent crossing across all this store's entrances.")

    @api.depends("device_ids", "register_ids")
    def _compute_counts(self):
        for store in self:
            store.device_count = len(store.device_ids)
            store.register_count = len(store.register_ids)

    def _period_window(self):
        """Return (start_utc, end_utc, is_today) for the selected period as
        naive UTC datetimes, computed on the user's timezone so 'today' /
        'this week' match the wall calendar. The period is read from the
        search context key 'ff_period' (today | yesterday | week | month);
        'today' (the default) leaves end open at 'now' for a live count."""
        period = self.env.context.get("ff_period", "today")
        tz = pytz.timezone(self.env.user.tz or "UTC")
        now_local = pytz.utc.localize(fields.Datetime.now()).astimezone(tz)
        day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

        def to_utc(dt):
            return dt.astimezone(pytz.utc).replace(tzinfo=None)

        if period == "yesterday":
            start = day_start - timedelta(days=1)
            return to_utc(start), to_utc(day_start), False
        if period == "week":
            start = day_start - timedelta(days=day_start.weekday())
            return to_utc(start), None, False
        if period == "month":
            start = day_start.replace(day=1)
            return to_utc(start), None, False
        # today (default) — live, open-ended
        return to_utc(day_start), None, True

    def _compute_live(self):
        Event = self.env["xb.footfall.event"]
        start, end, _is_today = self._period_window()
        devices = self.mapped("device_ids")
        if not devices:
            for store in self:
                store.visitors_in = store.visitors_out = 0
                store.live_occupancy = 0
                store.last_event_time = False
            return
        dev_store = {d.id: d.store_id.id for d in devices}
        # visitors in/out over the period, per device+direction
        domain = [("device_id", "in", devices.ids), ("event_time", ">=", start)]
        if end:
            domain.append(("event_time", "<", end))
        grouped = Event._read_group(
            domain, groupby=["device_id", "direction"], aggregates=["count:sum"])
        ins = {}
        outs = {}
        for device, direction, total in grouped:
            sid = dev_store.get(device.id)
            if direction == "in":
                ins[sid] = ins.get(sid, 0) + (total or 0)
            elif direction == "out":
                outs[sid] = outs.get(sid, 0) + (total or 0)
        # most recent crossing per store (all time)
        seen = Event._read_group(
            [("device_id", "in", devices.ids)],
            groupby=["device_id"], aggregates=["event_time:max"])
        last = {}
        for device, ts in seen:
            sid = dev_store.get(device.id)
            if ts and (sid not in last or ts > last[sid]):
                last[sid] = ts
        for store in self:
            vin = ins.get(store.id, 0)
            vout = outs.get(store.id, 0)
            store.visitors_in = vin
            store.visitors_out = vout
            store.live_occupancy = max(vin - vout, 0)
            store.last_event_time = last.get(store.id, False)

    @api.constrains("register_ids")
    def _check_register_single_store(self):
        """A POS register may belong to at most one footfall store, otherwise
        its tickets would be double-counted across stores."""
        for store in self:
            for reg in store.register_ids:
                other = self.search([
                    ("id", "!=", store.id),
                    ("register_ids", "in", reg.id),
                ], limit=1)
                if other:
                    raise ValidationError(_(
                        "Register '%(reg)s' is already assigned to store "
                        "'%(store)s'. A register can belong to only one store.",
                        reg=reg.display_name, store=other.display_name))

    def action_view_devices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Devices"),
            "res_model": "xb.footfall.device",
            "view_mode": "list,form",
            "domain": [("store_id", "=", self.id)],
            "context": {"default_store_id": self.id},
        }
