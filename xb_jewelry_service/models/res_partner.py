from odoo import _, api, fields, models


class ResPartner(models.Model):
    """Jewellers are contacts, not a separate registry.

    External ones are already vendors, so they get invoiced and paid with
    standard Odoo; internal ones simply point at their employee record.
    """

    _inherit = "res.partner"

    is_jeweler = fields.Boolean(string="Is a jeweler")
    jeweler_type = fields.Selection(
        [
            ("internal", "Employee"),
            ("external", "External workshop"),
        ],
        default="external",
    )
    jeweler_service_ids = fields.Many2many(
        "product.product",
        "xb_jeweler_service_rel",
        "partner_id",
        "product_id",
        string="Specialties",
        domain="[('type', '=', 'service')]",
        help="Jobs this jeweler takes. Used to suggest who to assign.",
    )
    jeweler_rate_ids = fields.One2many(
        "xb.jeweler.rate", "partner_id", string="Rate card"
    )
    jeweler_scrap_tolerance_custom = fields.Boolean(
        string="Custom scrap tolerance",
        help="Tick to give this jeweler a tolerance of their own instead of "
        "the company default.",
    )
    jeweler_scrap_tolerance = fields.Float(
        string="Scrap tolerance (%)",
        help="Accepted loss on metal handed to this jeweler.",
    )
    jeweler_id_document = fields.Binary(string="ID document", attachment=True)
    jeweler_id_document_name = fields.Char()
    jeweler_open_repair_count = fields.Integer(
        compute="_compute_jeweler_stats", string="Open jobs"
    )
    jeweler_avg_rating = fields.Float(
        compute="_compute_jeweler_stats", string="Avg. workmanship", digits=(3, 2)
    )
    jeweler_rework_rate = fields.Float(
        compute="_compute_jeweler_stats",
        string="Rework rate (%)",
        digits=(5, 2),
        help="Share of jobs that had to be sent back for quality.",
    )

    def _compute_jeweler_stats(self):
        Repair = self.env["repair.order"]
        jewelers = self.filtered("is_jeweler")
        (self - jewelers).update(
            {
                "jeweler_open_repair_count": 0,
                "jeweler_avg_rating": 0.0,
                "jeweler_rework_rate": 0.0,
            }
        )
        if not jewelers:
            return
        # One read for every jeweler on screen instead of a search each.
        orders_by_jeweler = {}
        for order in Repair.search([("jeweler_id", "in", jewelers.ids)]):
            orders_by_jeweler.setdefault(order.jeweler_id.id, []).append(order)
        for partner in jewelers:
            orders = orders_by_jeweler.get(partner.id, [])
            partner.jeweler_open_repair_count = sum(
                1 for r in orders if r.state not in ("delivered", "cancel")
            )
            rated = [r for r in orders if r.qc_rating]
            partner.jeweler_avg_rating = (
                sum(int(r.qc_rating) for r in rated) / len(rated) if rated else 0.0
            )
            # Counted over jobs that actually finished, using the counter each
            # order carries: the state only says where a piece is right now, so
            # measuring rework by state reads zero as soon as it is fixed.
            finished = [r for r in orders if r.state in ("done", "delivered")]
            sent_back = sum(1 for r in finished if r.rework_count)
            partner.jeweler_rework_rate = (
                (sent_back / len(finished)) * 100 if finished else 0.0
            )

    def action_view_jeweler_repairs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "repair.order",
            "name": _("Jobs of %s", self.display_name),
            "view_mode": "list,form",
            "domain": [("jeweler_id", "=", self.id)],
        }
