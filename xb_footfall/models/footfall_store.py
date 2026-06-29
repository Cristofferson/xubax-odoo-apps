# -*- coding: utf-8 -*-
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
    note = fields.Text(string="Notes")

    @api.depends("device_ids", "register_ids")
    def _compute_counts(self):
        for store in self:
            store.device_count = len(store.device_ids)
            store.register_count = len(store.register_ids)

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
