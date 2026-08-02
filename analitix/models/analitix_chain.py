# -*- coding: utf-8 -*-
"""Chains, regions, and the two decisions that only a chain has to make.

Phases 1-6 sell to a shop. This one sells to a company that owns two hundred of
them, and the difference is not size — it is that a chain has questions a single
store cannot ask ("which of my branches converts worst, and is it the floor or
the footfall?") and powers a single store cannot abuse.

Structure
---------
``analitix.brand`` → ``analitix.region`` → ``analitix.store``, with no fixed
limit at any level. A single-store customer creates neither and nothing changes
for them: every field added here is optional and every default is the behaviour
they already had.

The two elevated decisions
--------------------------
Both are about **how far data reaches**, and both are deliberately taken out of
a store manager's hands (task 983, point 4; task 984's elevated control):

* **Face recognition scope.** By default a person recognised in branch A is not
  correlated with their visit to branch B. Turning that on builds a
  chain-wide picture of an individual's movements across a company's
  properties, which is a categorically larger thing than what any single store
  agreed to. It takes the highest corporate role, and it is audited.

* **Watch-list scope.** The opposite default, for the opposite reason: if
  somebody caused an incident at one branch it is reasonable that the others
  know. But it is still a chain-wide claim about a named person, so widening or
  narrowing it takes the same role and the same audit entry.

Neither is a switch a regional manager can flip on a Tuesday.
"""
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AnalitixBrand(models.Model):
    """A chain. The top of the tree, and where chain-wide decisions live."""
    _name = "analitix.brand"
    _description = "Analitix Chain"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(string="Reference", index=True, copy=False)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", string="Company", required=True, index=True,
        default=lambda self: self.env.company)

    region_ids = fields.One2many("analitix.region", "brand_id", string="Regions")
    store_ids = fields.One2many("analitix.store", "brand_id", string="Stores")
    region_count = fields.Integer(compute="_compute_counts")
    store_count = fields.Integer(compute="_compute_counts")

    # --- the elevated decisions (task 983, point 4) ---
    reid_scope = fields.Selection(
        selection=[
            ("store", "Each store on its own"),
            ("chain", "Across the whole chain"),
        ],
        string="Recognition Scope", default="store", required=True,
        tracking=True,
        help="Whether a recognised customer is correlated across branches.\n"
             "'Each store on its own' is the default and the smaller claim: a "
             "person seen in one branch is not linked to their visit to "
             "another.\n"
             "'Across the whole chain' builds a picture of one individual's "
             "movements between your properties. It is a categorically larger "
             "thing than store-level recognition, so only the corporate role "
             "can switch it and the change is recorded in the audit log.")
    watchlist_scope = fields.Selection(
        selection=[
            ("chain", "Shared across the chain"),
            ("store", "Each store on its own"),
        ],
        string="Watch-list Scope", default="chain", required=True,
        tracking=True,
        help="Shared by default, and for a reason: if somebody caused an "
             "incident at one branch it is reasonable that the others know. It "
             "is still a chain-wide statement about a named person, so "
             "changing this either way takes the corporate role and is "
             "audited.")

    scope_changed_by_id = fields.Many2one(
        "res.users", string="Scope Last Changed By", readonly=True)
    scope_changed_on = fields.Datetime(string="Scope Last Changed", readonly=True)

    _code_uniq = models.Constraint(
        "unique(code, company_id)",
        "That chain reference already exists in this company.")

    @api.depends("region_ids", "store_ids")
    def _compute_counts(self):
        for brand in self:
            brand.region_count = len(brand.region_ids)
            brand.store_count = len(brand.store_ids)

    # ------------------------------------------------------------------
    def write(self, vals):
        """Guard the two scope fields, and record who moved them.

        Written as a guard on ``write`` rather than as a button so it cannot be
        bypassed by a bulk edit, an import, or an automated action — the three
        ways a control that lives only in the UI is usually defeated.
        """
        scoped = {"reid_scope", "watchlist_scope"} & set(vals)
        if scoped and not self.env.su:
            if not self.env.user.has_group("analitix.group_corporate"):
                raise UserError(_(
                    "Only the corporate role can change how far recognition "
                    "reaches across a chain. This decides whether one person's "
                    "movements are correlated between your branches, which is "
                    "not a store or regional setting."))
            vals = dict(vals, scope_changed_by_id=self.env.user.id,
                        scope_changed_on=fields.Datetime.now())

        before = {brand.id: (brand.reid_scope, brand.watchlist_scope)
                  for brand in self} if scoped else {}
        result = super().write(vals)

        for brand in self if scoped else self.browse():
            was_reid, was_watch = before.get(brand.id, (None, None))
            for field, old, new, label in (
                    ("reid_scope", was_reid, brand.reid_scope,
                     _("face recognition")),
                    ("watchlist_scope", was_watch, brand.watchlist_scope,
                     _("watch list"))):
                if field in vals and old != new:
                    self.env["analitix.audit.log"].sudo().log(
                        action="elevated", model=self._name, res_id=brand.id,
                        note=_("Chain %(brand)s: %(what)s scope changed from "
                               "%(old)s to %(new)s",
                               brand=brand.name, what=label, old=old, new=new))
                    brand.message_post(body=_(
                        "%(user)s changed the %(what)s scope from "
                        "<b>%(old)s</b> to <b>%(new)s</b> for the whole chain.",
                        user=self.env.user.display_name, what=label,
                        old=old, new=new))
        return result

    def action_view_stores(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Stores"),
            "res_model": "analitix.store",
            "view_mode": "list,form",
            "domain": [("brand_id", "=", self.id)],
        }


class AnalitixRegion(models.Model):
    """A district. Groups stores so a regional manager has a scope.

    Deliberately one level and not a self-referencing tree: a nested hierarchy
    is easy to model and very hard to write a correct record rule against, and
    an incorrect record rule on this model is a data leak between a company's
    own districts. If a customer genuinely needs three levels, a brand above
    regions already gives two — and a third should be built when somebody is
    actually paying for it, with tests, rather than speculatively now.
    """
    _name = "analitix.region"
    _description = "Analitix Region"
    _inherit = ["mail.thread"]
    _order = "brand_id, name"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(string="Reference", index=True, copy=False)
    active = fields.Boolean(default=True)
    brand_id = fields.Many2one(
        "analitix.brand", string="Chain", required=True, index=True,
        ondelete="cascade", tracking=True)
    company_id = fields.Many2one(
        "res.company", related="brand_id.company_id", store=True, index=True,
        readonly=True)
    manager_id = fields.Many2one(
        "res.users", string="Regional Manager", tracking=True,
        help="Informational. What actually grants access is the region on the "
             "user's own Analitix scope — a name in this field alone opens "
             "nothing, on purpose.")

    store_ids = fields.One2many("analitix.store", "region_id", string="Stores")
    store_count = fields.Integer(compute="_compute_store_count")

    _code_uniq = models.Constraint(
        "unique(code, brand_id)",
        "That region reference already exists in this chain.")

    @api.depends("store_ids")
    def _compute_store_count(self):
        for region in self:
            region.store_count = len(region.store_ids)


class AnalitixStore(models.Model):
    _inherit = "analitix.store"

    region_id = fields.Many2one(
        "analitix.region", string="Region", index=True, ondelete="set null",
        tracking=True,
        help="Optional. A single-store customer leaves this empty and nothing "
             "about their installation changes.")
    brand_id = fields.Many2one(
        "analitix.brand", string="Chain", index=True, ondelete="set null",
        tracking=True,
        help="Set directly, or filled in from the region. A store belongs to "
             "at most one chain.")

    _region_idx = models.Index("(region_id)")
    _brand_idx = models.Index("(brand_id)")

    @api.onchange("region_id")
    def _onchange_region(self):
        if self.region_id:
            self.brand_id = self.region_id.brand_id

    @api.constrains("region_id", "brand_id")
    def _check_region_matches_brand(self):
        """A store cannot sit in one chain's region while flying another's flag.

        It would silently break every rollup: the region's report would include
        it and the chain's would not, and nobody would know which figure was
        wrong.
        """
        for store in self:
            if store.region_id and store.brand_id and \
                    store.region_id.brand_id != store.brand_id:
                raise ValidationError(_(
                    "Store '%(store)s' is in region '%(region)s', which belongs "
                    "to chain '%(their)s', but the store is assigned to chain "
                    "'%(ours)s'.",
                    store=store.display_name, region=store.region_id.name,
                    their=store.region_id.brand_id.name,
                    ours=store.brand_id.name))

    # ------------------------------------------------------------------
    # Scope helpers, used by recognition and by the watch list
    # ------------------------------------------------------------------
    def _reid_scope_store_ids(self):
        """Stores whose face signatures this store may be matched against.

        Itself, always. The rest of the chain only when a corporate user has
        deliberately widened the scope — which is why this reads the brand's
        setting rather than accepting a parameter from the caller.
        """
        self.ensure_one()
        if self.brand_id and self.brand_id.reid_scope == "chain":
            return self.search([("brand_id", "=", self.brand_id.id)]).ids
        return self.ids

    def _watchlist_scope_store_ids(self):
        """Stores whose watch-list entries apply here.

        The default is the other way round from recognition: shared across the
        chain, because an incident at one branch is worth the others knowing.
        """
        self.ensure_one()
        if self.brand_id and self.brand_id.watchlist_scope == "chain":
            return self.search([("brand_id", "=", self.brand_id.id)]).ids
        return self.ids
