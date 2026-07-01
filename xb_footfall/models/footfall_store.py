# -*- coding: utf-8 -*-
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
        "xb.footfall.device", "store_id", string="Entrances / Devices")
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
    # --- Live occupancy (today, in the user's timezone) ---
    visitors_today = fields.Integer(
        string="Visitors Today", compute="_compute_live", compute_sudo=True,
        help="People who have entered the store since midnight (your timezone).")
    exits_today = fields.Integer(
        string="Exits Today", compute="_compute_live", compute_sudo=True)
    live_occupancy = fields.Integer(
        string="Live Occupancy", compute="_compute_live", compute_sudo=True,
        help="People currently inside: entrances minus exits so far today "
             "(never negative). A live estimate, reset every midnight.")
    last_event_time = fields.Datetime(
        string="Last Event", compute="_compute_live", compute_sudo=True,
        help="Time of the most recent crossing across all this store's entrances.")

    @api.depends("device_ids", "register_ids")
    def _compute_counts(self):
        for store in self:
            store.device_count = len(store.device_ids)
            store.register_count = len(store.register_ids)

    def _today_start_utc(self):
        """Midnight of the current local day, as a naive UTC datetime, so the
        'today' window matches what the manager sees on the wall clock."""
        tz = pytz.timezone(self.env.user.tz or "UTC")
        now_local = pytz.utc.localize(fields.Datetime.now()).astimezone(tz)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_local.astimezone(pytz.utc).replace(tzinfo=None)

    def _compute_live(self):
        Event = self.env["xb.footfall.event"]
        devices = self.mapped("device_ids")
        if not devices:
            for store in self:
                store.visitors_today = store.exits_today = 0
                store.live_occupancy = 0
                store.last_event_time = False
            return
        start = self._today_start_utc()
        dev_store = {d.id: d.store_id.id for d in devices}
        # visitors in/out today, per device+direction
        today = Event._read_group(
            [("device_id", "in", devices.ids), ("event_time", ">=", start)],
            groupby=["device_id", "direction"], aggregates=["count:sum"])
        ins = {}
        outs = {}
        for device, direction, total in today:
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
            store.visitors_today = vin
            store.exits_today = vout
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
            "name": _("Entrances"),
            "res_model": "xb.footfall.device",
            "view_mode": "list,form",
            "domain": [("store_id", "=", self.id)],
            "context": {"default_store_id": self.id},
        }
