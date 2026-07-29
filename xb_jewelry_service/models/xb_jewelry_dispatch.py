from odoo import _, api, fields, models
from odoo.exceptions import UserError


class XbJewelryDispatch(models.Model):
    """Hand-over of one or more pieces to a jeweler.

    Kept apart from the repair order on purpose: the usual case is a jeweler
    taking a whole order, but a single order can be split across jewelers by
    specialty, and one jeweler can take pieces from several customers at once.
    """

    _name = "xb.jewelry.dispatch"
    _description = "Workshop Dispatch"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        required=True, copy=False, readonly=True, default=lambda self: _("New")
    )
    jeweler_id = fields.Many2one(
        "res.partner",
        required=True,
        domain="[('is_jeweler', '=', True)]",
        tracking=True,
        index=True,
    )
    date = fields.Datetime(default=fields.Datetime.now, required=True, tracking=True)
    return_date = fields.Datetime(readonly=True, copy=False)
    promised_date = fields.Date(
        tracking=True,
        help="Date the jeweler commits to when taking the pieces.",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("out", "At workshop"),
            ("returned", "Returned"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        tracking=True,
    )
    repair_ids = fields.One2many("repair.order", "dispatch_id", string="Pieces")
    repair_count = fields.Integer(compute="_compute_repair_count")
    user_id = fields.Many2one(
        "res.users", string="Responsible", default=lambda self: self.env.user
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )

    signature = fields.Image(
        string="Jeweler signature", max_width=1024, max_height=1024, copy=False
    )
    signed_by = fields.Char(copy=False)
    signed_on = fields.Datetime(copy=False)

    # --- Material and scrap --------------------------------------------
    material_line_ids = fields.One2many(
        "xb.jewelry.dispatch.material", "dispatch_id", string="Material handed over"
    )
    scrap_tolerance = fields.Float(
        string="Scrap tolerance (%)",
        compute="_compute_scrap_tolerance",
        store=True,
        readonly=False,
        help="Inherited from the jeweler, or from the company when the jeweler "
        "has no specific tolerance. Override it here for this hand-over only.",
    )
    material_out_g = fields.Float(
        string="Handed over (g)", compute="_compute_material_totals", store=True,
        digits=(12, 3)
    )
    customer_gold_g = fields.Float(
        string="Customer's gold (g)",
        compute="_compute_material_totals",
        store=True,
        digits=(12, 3),
        help="Metal the customer brought in for a commission or a "
        "transformation. It leaves with the jeweler like the shop's own "
        "material, and has to come back the same way.",
    )
    scrap_back_g = fields.Float(
        string="Scrap returned (g)", compute="_compute_material_totals", store=True,
        digits=(12, 3)
    )
    weight_gain_g = fields.Float(
        string="Added to pieces (g)",
        compute="_compute_material_totals",
        store=True,
        digits=(12, 3),
        help="How much heavier the pieces came back, which is metal that "
        "legitimately stayed in the work.",
    )
    loss_g = fields.Float(
        string="Loss (g)", compute="_compute_material_totals", store=True,
        digits=(12, 3)
    )
    loss_pct = fields.Float(
        string="Loss (%)", compute="_compute_material_totals", store=True,
        digits=(5, 2)
    )
    within_tolerance = fields.Boolean(
        compute="_compute_material_totals", store=True
    )
    note = fields.Html()

    @api.depends("jeweler_id", "company_id")
    def _compute_scrap_tolerance(self):
        for dispatch in self:
            jeweler = dispatch.jeweler_id
            if jeweler.jeweler_scrap_tolerance_custom:
                dispatch.scrap_tolerance = jeweler.jeweler_scrap_tolerance
            else:
                dispatch.scrap_tolerance = (
                    dispatch.company_id or self.env.company
                ).xb_scrap_tolerance

    @api.depends(
        "material_line_ids.qty_out_g",
        "material_line_ids.qty_back_g",
        "repair_ids.weight_after_g",
        "repair_ids.jewelry_piece_id.weight_g",
        "repair_ids.xb_input_piece_ids.weight_g",
        "scrap_tolerance",
    )
    def _compute_material_totals(self):
        for dispatch in self:
            shop_out = sum(dispatch.material_line_ids.mapped("qty_out_g"))
            back = sum(dispatch.material_line_ids.mapped("qty_back_g"))
            gain = 0.0
            customer = 0.0
            for repair in dispatch.repair_ids:
                after = repair.weight_after_g
                if repair.xb_service_type == "repair":
                    before = repair.jewelry_piece_id.weight_g
                    if before and after and after > before:
                        gain += after - before
                elif after:
                    # A commission has no "before": the finished piece IS the
                    # metal that stayed in the work, all of it.
                    gain += after
                # Gold the customer brought to be melted down is material
                # handed to the jeweler just the same, and the shop answers
                # for it to the customer.
                customer += sum(repair.xb_input_piece_ids.mapped("weight_g"))
            out = shop_out + customer
            dispatch.customer_gold_g = customer
            dispatch.material_out_g = out
            dispatch.scrap_back_g = back
            dispatch.weight_gain_g = gain
            loss = out - back - gain
            dispatch.loss_g = loss
            dispatch.loss_pct = (loss / out * 100) if out else 0.0
            dispatch.within_tolerance = (
                dispatch.loss_pct <= dispatch.scrap_tolerance if out else True
            )

    def _compute_repair_count(self):
        for dispatch in self:
            dispatch.repair_count = len(dispatch.repair_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("New"):
                company_id = vals.get("company_id") or self.env.company.id
                vals["name"] = self.env["ir.sequence"].with_company(
                    company_id
                ).next_by_code("xb.jewelry.dispatch") or _("New")
        return super().create(vals_list)

    # --- Transitions ---------------------------------------------------
    def action_dispatch(self):
        company = self.company_id or self.env.company
        for dispatch in self:
            if not dispatch.repair_ids:
                raise UserError(
                    _("Add at least one piece to %(ref)s.", ref=dispatch.name)
                )
            if company.xb_require_dispatch_signature and not dispatch.signature:
                raise UserError(
                    _(
                        "The jeweler must sign for %(ref)s before taking the "
                        "pieces.",
                        ref=dispatch.name,
                    )
                )
            dispatch.repair_ids.write(
                {
                    "jeweler_id": dispatch.jeweler_id.id,
                    "jeweler_promised_date": dispatch.promised_date,
                }
            )
            # Each piece keeps its own guard: photos and the customer
            # signature are checked one by one here.
            dispatch.repair_ids.action_repair_start()
            dispatch.state = "out"
        return True

    def action_return(self):
        for dispatch in self:
            if dispatch.state != "out":
                raise UserError(_("%(ref)s is not at the workshop.", ref=dispatch.name))
            dispatch.repair_ids.filtered(
                lambda r: r.state in ("under_repair", "rework")
            ).action_receive_from_workshop()
            dispatch.write(
                {"state": "returned", "return_date": fields.Datetime.now()}
            )
            if not dispatch.within_tolerance:
                dispatch.message_post(
                    body=_(
                        "Metal loss is %(loss)s%%, above the %(tol)s%% tolerance "
                        "agreed with this jeweler.",
                        loss=round(dispatch.loss_pct, 2),
                        tol=dispatch.scrap_tolerance,
                    ),
                    message_type="comment",
                )
        return True

    def action_cancel(self):
        return self.write({"state": "cancel"})

    def action_view_repairs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "repair.order",
            "name": _("Pieces of %s", self.name),
            "view_mode": "list,form",
            "domain": [("dispatch_id", "=", self.id)],
        }


class XbJewelryDispatchMaterial(models.Model):
    """Metal the shop hands to the jeweler, and what comes back."""

    _name = "xb.jewelry.dispatch.material"
    _description = "Dispatch Material"

    dispatch_id = fields.Many2one(
        "xb.jewelry.dispatch", required=True, ondelete="cascade"
    )
    product_id = fields.Many2one("product.product", string="Material", required=True)
    metal_value_id = fields.Many2one(
        "product.attribute.value", string="Metal"
    )
    purity = fields.Float(
        digits=(4, 4),
        compute="_compute_purity",
        store=True,
        readonly=False,
    )
    qty_out_g = fields.Float(string="Handed over (g)", digits=(12, 3), required=True)
    qty_back_g = fields.Float(string="Returned (g)", digits=(12, 3))
    pure_out_g = fields.Float(
        string="Pure out (g)", compute="_compute_pure", store=True, digits=(12, 3)
    )
    pure_back_g = fields.Float(
        string="Pure back (g)", compute="_compute_pure", store=True, digits=(12, 3)
    )

    @api.depends("metal_value_id")
    def _compute_purity(self):
        purities = self.env["xb.metal.purity"].search(
            [("attribute_value_id", "in", self.metal_value_id.ids)]
        )
        by_value = {p.attribute_value_id.id: p.purity for p in purities}
        for line in self:
            line.purity = by_value.get(line.metal_value_id.id, 0.0)

    @api.depends("qty_out_g", "qty_back_g", "purity")
    def _compute_pure(self):
        for line in self:
            line.pure_out_g = line.qty_out_g * line.purity
            line.pure_back_g = line.qty_back_g * line.purity
