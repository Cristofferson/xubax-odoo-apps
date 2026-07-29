from odoo import _, api, fields, models
from odoo.exceptions import UserError


class XbJewelerSettlement(models.Model):
    """What the shop owes a jeweler, settled per piece or per period.

    Per piece is just a settlement with a single line, so the shop can pay on
    delivery for some jewelers and run a weekly cut for others without two
    different mechanisms.
    """

    _name = "xb.jeweler.settlement"
    _description = "Jeweler Settlement"
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
    jeweler_type = fields.Selection(related="jeweler_id.jeweler_type")
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("paid", "Paid"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        tracking=True,
    )
    repair_ids = fields.One2many("repair.order", "settlement_id", string="Jobs")
    job_count = fields.Integer(compute="_compute_amount_total")
    amount_total = fields.Monetary(
        compute="_compute_amount_total", store=True, currency_field="currency_id"
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    move_id = fields.Many2one(
        "account.move", string="Vendor bill", readonly=True, copy=False
    )
    note = fields.Html()

    @api.depends("repair_ids.jeweler_cost")
    def _compute_amount_total(self):
        for settlement in self:
            settlement.amount_total = sum(settlement.repair_ids.mapped("jeweler_cost"))
            settlement.job_count = len(settlement.repair_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("New"):
                company_id = vals.get("company_id") or self.env.company.id
                vals["name"] = self.env["ir.sequence"].with_company(
                    company_id
                ).next_by_code("xb.jeweler.settlement") or _("New")
        return super().create(vals_list)

    def action_gather_jobs(self):
        """Pull in every finished job of this jeweler that nobody has paid yet."""
        for settlement in self:
            jobs = self.env["repair.order"].search(
                [
                    ("jeweler_id", "=", settlement.jeweler_id.id),
                    ("company_id", "=", settlement.company_id.id),
                    ("settlement_id", "=", False),
                    ("state", "in", ("done", "delivered")),
                    ("qc_date", ">=", settlement.date_from),
                    ("qc_date", "<=", fields.Datetime.to_datetime(
                        settlement.date_to).replace(hour=23, minute=59, second=59)),
                ]
            )
            if not jobs:
                raise UserError(
                    _("No unpaid finished jobs for this jeweler in that period.")
                )
            jobs.settlement_id = settlement.id
        return True

    def action_confirm(self):
        for settlement in self:
            if not settlement.repair_ids:
                raise UserError(_("There is nothing to settle in %(ref)s.",
                                  ref=settlement.name))
            settlement.state = "confirmed"
            if settlement.jeweler_type == "external":
                settlement._create_vendor_bill()
        return True

    def _create_vendor_bill(self):
        self.ensure_one()
        if self.move_id:
            return self.move_id
        fallback = self.company_id.xb_jeweler_service_product_id
        lines = []
        for repair in self.repair_ids:
            if not repair.jeweler_cost:
                continue
            product = repair.sale_order_line_id.product_id or fallback
            if not product:
                raise UserError(
                    _(
                        "Set a default jeweler service product in the settings "
                        "so the vendor bill can be built."
                    )
                )
            lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "name": _("%(repair)s - %(piece)s",
                                  repair=repair.name,
                                  piece=repair.jewelry_piece_id.description or ""),
                        "quantity": 1,
                        "price_unit": repair.jeweler_cost,
                    },
                )
            )
        if not lines:
            raise UserError(_("Every job in %(ref)s has a zero rate.",
                              ref=self.name))
        move = self.env["account.move"].with_company(self.company_id).create(
            {
                "move_type": "in_invoice",
                "partner_id": self.jeweler_id.id,
                "invoice_date": self.date_to,
                "invoice_origin": self.name,
                "invoice_line_ids": lines,
            }
        )
        self.move_id = move.id
        return move

    def action_mark_paid(self):
        return self.write({"state": "paid"})

    def action_cancel(self):
        for settlement in self:
            settlement.repair_ids.settlement_id = False
            settlement.state = "cancel"
        return True

    def action_view_bill(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
        }
