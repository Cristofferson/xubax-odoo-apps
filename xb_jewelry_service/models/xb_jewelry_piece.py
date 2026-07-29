from odoo import _, api, fields, models


class XbJewelryPiece(models.Model):
    """The customer's piece, as a permanent file.

    Deliberately not a line of the repair order: the same ring comes back for
    service years later, and the customer may later ask for an appraisal or
    put it on consignment. The repair is an episode, the piece is the record.
    """

    _name = "xb.jewelry.piece"
    _description = "Jewelry Piece"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        index="trigram",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Owner",
        required=True,
        index=True,
        tracking=True,
        help="The piece belongs to this customer at all times. "
        "It never becomes shop property.",
    )
    description = fields.Char(required=True, tracking=True)
    piece_type_id = fields.Many2one(
        "product.category",
        string="Piece type",
        tracking=True,
        domain="[('xb_jewelry_kind', '!=', False)]",
        help="Taken from the shop's own product categories, so the vocabulary "
        "is the same one used in the catalogue. Left empty for scrap gold a "
        "customer brings in to be melted down, which belongs to no category "
        "of the catalogue and never will.",
    )
    piece_kind = fields.Selection(
        related="piece_type_id.xb_jewelry_kind",
        store=True,
        help="Decides which measurements and photos the piece needs.",
    )

    # --- Metal, reusing the shop's own product attribute ---------------
    metal_value_id = fields.Many2one(
        "product.attribute.value",
        string="Metal",
        tracking=True,
        domain="[('attribute_id', '=', metal_attribute_id)]",
        help="Taken from the same attribute used to create products, "
        "so the vocabulary stays consistent across the company.",
    )
    metal_attribute_id = fields.Many2one(
        "product.attribute",
        compute="_compute_metal_attribute_id",
    )
    purity = fields.Float(
        digits=(4, 4),
        compute="_compute_purity",
        store=True,
        readonly=False,
        help="Fineness as a number. Filled in from the metal, "
        "override it when the piece has been tested.",
    )
    weight_g = fields.Float(string="Weight (g)", digits=(12, 3), tracking=True)
    pure_metal_weight_g = fields.Float(
        string="Pure metal (g)",
        digits=(12, 3),
        compute="_compute_pure_metal_weight",
        store=True,
    )

    # --- Measurements --------------------------------------------------
    size_value_id = fields.Many2one(
        "product.attribute.value",
        string="Size",
        domain="[('attribute_id', '=', size_attribute_id)]",
        help="Only meaningful for rings. Uses the same size list as the catalogue.",
    )
    size_attribute_id = fields.Many2one(
        "product.attribute",
        compute="_compute_metal_attribute_id",
    )
    length_cm = fields.Float(
        string="Length (cm)",
        digits=(12, 2),
        help="Only meaningful for chains and bracelets.",
    )
    stone_count = fields.Integer()
    has_diamond = fields.Boolean(tracking=True)
    diamond_tester = fields.Selection(
        [
            ("pass", "Passed"),
            ("fail", "Failed"),
        ],
        string="Diamond tester",
        tracking=True,
        help="Result of the tester at intake. Comparing it against the "
        "reading taken when the piece comes back is what catches a swap.",
    )
    has_laser_inscription = fields.Boolean(
        string="Laser inscribed",
        help="Tick when the stone carries an inscription. Only then is a "
        "photograph of it worth asking for.",
    )
    laser_inscription = fields.Char(
        help="Inscription number on the stone, when it has one.",
    )

    # --- Custody -------------------------------------------------------
    custody_state = fields.Selection(
        [
            ("with_customer", "With customer"),
            ("in_custody", "In custody"),
            ("at_workshop", "At workshop"),
            ("ready", "Ready for pickup"),
        ],
        compute="_compute_custody_state",
        store=True,
        tracking=True,
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Serial",
        copy=False,
        help="Optional. Links the piece to a serial number so its movements "
        "are traced by Inventory.",
    )
    photo_ids = fields.One2many("xb.jewelry.photo", "piece_id", string="Photos")
    photo_count = fields.Integer(compute="_compute_photo_count")
    repair_order_ids = fields.One2many(
        "repair.order", "jewelry_piece_id", string="Service history"
    )
    repair_count = fields.Integer(compute="_compute_repair_count")
    note = fields.Html()
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)

    @api.depends_context("company")
    def _compute_metal_attribute_id(self):
        for piece in self:
            company = piece.company_id or self.env.company
            piece.metal_attribute_id = company.xb_metal_attribute_id
            piece.size_attribute_id = company.xb_size_attribute_id

    @api.depends("metal_value_id")
    def _compute_purity(self):
        purities = self.env["xb.metal.purity"].search(
            [("attribute_value_id", "in", self.metal_value_id.ids)]
        )
        by_value = {p.attribute_value_id.id: p.purity for p in purities}
        for piece in self:
            piece.purity = by_value.get(piece.metal_value_id.id, 0.0)

    @api.depends("weight_g", "purity")
    def _compute_pure_metal_weight(self):
        for piece in self:
            piece.pure_metal_weight_g = piece.weight_g * piece.purity

    @api.depends("repair_order_ids.state")
    def _compute_custody_state(self):
        for piece in self:
            open_orders = piece.repair_order_ids.filtered(
                lambda r: r.state not in ("delivered", "cancel")
            )
            if not open_orders:
                piece.custody_state = "with_customer"
            elif any(r.state == "under_repair" for r in open_orders):
                piece.custody_state = "at_workshop"
            elif all(r.state == "done" for r in open_orders):
                piece.custody_state = "ready"
            else:
                piece.custody_state = "in_custody"

    def _compute_photo_count(self):
        data = self.env["xb.jewelry.photo"]._read_group(
            [("piece_id", "in", self.ids)], ["piece_id"], ["__count"]
        )
        counts = {piece.id: count for piece, count in data}
        for piece in self:
            piece.photo_count = counts.get(piece.id, 0)

    def _compute_repair_count(self):
        data = self.env["repair.order"]._read_group(
            [("jewelry_piece_id", "in", self.ids)], ["jewelry_piece_id"], ["__count"]
        )
        counts = {piece.id: count for piece, count in data}
        for piece in self:
            piece.repair_count = counts.get(piece.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("New"):
                company_id = vals.get("company_id") or self.env.company.id
                vals["name"] = self.env["ir.sequence"].with_company(
                    company_id
                ).next_by_code("xb.jewelry.piece") or _("New")
        return super().create(vals_list)

    @api.depends("name", "description")
    def _compute_display_name(self):
        """A reference alone tells nobody which ring it is.

        The board, the POS list and the portal all show the piece by its
        display name, and "PCE/2026/00039" is not something anyone at the
        counter can match to what is in their hand.
        """
        for piece in self:
            piece.display_name = (
                f"{piece.name} - {piece.description}"
                if piece.description
                else piece.name
            )

    def _compute_access_url(self):
        super()._compute_access_url()
        for piece in self:
            piece.access_url = f"/my/jewelry/{piece.id}"

    def action_view_repairs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "repair.order",
            "name": _("Services of %s", self.name),
            "view_mode": "list,form",
            "domain": [("jewelry_piece_id", "=", self.id)],
            "context": {"default_jewelry_piece_id": self.id,
                        "default_partner_id": self.partner_id.id},
        }
