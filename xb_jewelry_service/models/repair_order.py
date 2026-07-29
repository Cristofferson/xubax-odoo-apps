from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RepairOrder(models.Model):
    """Jewellery layer on top of the native repair order.

    The native states are kept and extended rather than replaced, so an
    upgrade of Odoo's own Repairs app does not take this module down with it.
    """

    _inherit = "repair.order"

    state = fields.Selection(
        selection_add=[
            ("draft",),
            ("pending_auth", "Pending Authorization"),
            ("confirmed",),
            ("under_repair",),
            ("inspection", "Inspection"),
            ("rework", "Rework"),
            ("done",),
            ("delivered", "Delivered"),
            ("cancel",),
        ],
        ondelete={
            "pending_auth": lambda recs: recs.write({"state": "draft"}),
            "inspection": lambda recs: recs.write({"state": "under_repair"}),
            "rework": lambda recs: recs.write({"state": "under_repair"}),
            "delivered": lambda recs: recs.write({"state": "done"}),
        },
    )

    xb_service_type = fields.Selection(
        [
            ("repair", "Repair"),
            ("custom", "Commission"),
            ("transform", "Transformation"),
        ],
        string="Kind of work",
        default="repair",
        required=True,
        tracking=True,
        help="A repair returns the same piece. A commission makes a new one, "
        "sometimes out of gold the customer brings in. A transformation melts "
        "the customer's own pieces into something else entirely.",
    )
    jewelry_piece_id = fields.Many2one(
        "xb.jewelry.piece",
        string="Piece",
        index=True,
        tracking=True,
        help="The piece this service is about: the one received for a repair, "
        "or the one being made for a commission.",
    )
    xb_input_piece_ids = fields.Many2many(
        "xb.jewelry.piece",
        "xb_repair_input_piece_rel",
        "repair_id",
        "piece_id",
        string="Customer's gold",
        help="Pieces the customer hands over to be melted down or reworked "
        "into the new one. They are in the shop's custody just like a repair, "
        "and their metal counts towards what the jeweler has to account for.",
    )
    xb_input_pure_g = fields.Float(
        string="Customer's pure metal (g)",
        compute="_compute_xb_input_pure_g",
        store=True,
        digits=(12, 3),
    )
    xb_spec = fields.Html(
        string="What to make",
        help="What the customer is commissioning, in enough detail that the "
        "jeweler and the customer are agreeing to the same thing.",
    )
    jeweler_id = fields.Many2one(
        "res.partner",
        string="Jeweler",
        domain="[('is_jeweler', '=', True)]",
        tracking=True,
        index=True,
    )
    jeweler_promised_date = fields.Date(
        string="Promised by jeweler",
        tracking=True,
        help="Date the jeweller commits to when the piece is handed over.",
    )
    jeweler_cost = fields.Monetary(
        string="Jeweler cost",
        currency_field="company_currency_id",
        compute="_compute_jeweler_cost",
        store=True,
        readonly=False,
        help="Agreed rate for this job. Filled in from the jeweler's rate "
        "card, and always editable for this particular piece.",
    )
    settlement_id = fields.Many2one(
        "xb.jeweler.settlement",
        string="Settlement",
        copy=False,
        readonly=True,
        index=True,
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", string="Company Currency"
    )
    dispatch_id = fields.Many2one(
        "xb.jewelry.dispatch",
        string="Workshop dispatch",
        copy=False,
        index=True,
        help="Hand-over document this piece left with.",
    )
    weight_after_g = fields.Float(
        string="Weight on return (g)",
        digits=(12, 3),
        copy=False,
        help="Weigh the piece again when it comes back. The difference "
        "against intake is metal that legitimately stayed in the work.",
    )
    weight_diff_g = fields.Float(
        string="Weight change (g)",
        compute="_compute_weight_diff",
        digits=(12, 3),
    )
    material_supplied_by = fields.Selection(
        [
            ("jeweler", "Jeweler"),
            ("shop", "Shop"),
        ],
        default="jeweler",
        help="Who provides the metal, solder and stones for this job.",
    )
    delay_days = fields.Integer(
        compute="_compute_delay_days",
        store=True,
        help="Days between the promised date and the actual completion.",
    )

    # The customer's own words. Odoo's native `repair_request` is a related
    # field on the sale order line, so it silently drops anything typed on an
    # order that has no line yet, which is exactly the case at the counter.
    xb_customer_request = fields.Text(
        string="What the customer asks for",
        tracking=True,
    )

    # --- Photos --------------------------------------------------------
    photo_ids = fields.One2many(
        "xb.jewelry.photo", "repair_id", string="Photos", copy=False
    )
    missing_photo_kind_ids = fields.Many2many(
        "xb.jewelry.photo.kind",
        string="Missing photos",
        compute="_compute_missing_photo_kind_ids",
        help="Everything still to be photographed before the piece may leave "
        "for the workshop.",
    )
    xb_intake_missing_kind_ids = fields.Many2many(
        "xb.jewelry.photo.kind",
        "xb_repair_intake_missing_kind_rel",
        string="Missing at the counter",
        compute="_compute_missing_photo_kind_ids",
        help="The subset the shop demands while the customer is still there. "
        "The rest can be taken afterwards, from a phone.",
    )

    # --- Signatures ----------------------------------------------------
    intake_signature = fields.Image(
        string="Customer signature (intake)", max_width=1024, max_height=1024, copy=False
    )
    intake_signed_by = fields.Char(copy=False)
    intake_signed_on = fields.Datetime(copy=False)
    delivery_signature = fields.Image(
        string="Customer signature (delivery)",
        max_width=1024,
        max_height=1024,
        copy=False,
    )
    delivery_signed_by = fields.Char(copy=False)
    delivery_signed_on = fields.Datetime(copy=False)

    # --- Quality control on return -------------------------------------
    qc_weight_ok = fields.Boolean(string="Weight matches", copy=False)
    qc_stones_ok = fields.Boolean(string="Stones complete", copy=False)
    qc_size_ok = fields.Boolean(string="Measurements correct", copy=False)
    qc_solder_ok = fields.Boolean(string="Soldering sound", copy=False)
    qc_finish_ok = fields.Boolean(string="Finish acceptable", copy=False)
    qc_tester_ok = fields.Boolean(
        string="Diamond tester passed",
        copy=False,
        help="Only required when the piece carries a diamond.",
    )
    qc_rating = fields.Selection(
        [("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5")],
        string="Workmanship",
        copy=False,
        help="Feeds the jeweller scorecard.",
    )
    qc_user_id = fields.Many2one(
        "res.users", string="Inspected by", readonly=True, copy=False
    )
    qc_date = fields.Datetime(readonly=True, copy=False)
    qc_note = fields.Text(string="Inspection notes", copy=False)

    # --- Warranty ------------------------------------------------------
    warranty_until = fields.Date(copy=False, tracking=True)
    origin_repair_id = fields.Many2one(
        "repair.order",
        string="Original service",
        copy=False,
        help="Set when this order redoes a previous one under warranty.",
    )
    warranty_repair_ids = fields.One2many(
        "repair.order",
        "origin_repair_id",
        string="Warranty claims",
        readonly=True,
    )
    warranty_claim_count = fields.Integer(compute="_compute_warranty_claim_count")
    warranty_active = fields.Boolean(
        compute="_compute_warranty_active",
        search="_search_warranty_active",
        help="The work on this piece is still covered.",
    )
    rework_count = fields.Integer(
        string="Times sent back",
        default=0,
        copy=False,
        readonly=True,
        help="How often this job failed inspection. Kept as a counter because "
        "the state only says where the piece is now, not what it went through.",
    )

    @api.depends("jeweler_id", "sale_order_line_id.product_id")
    def _compute_jeweler_cost(self):
        Rate = self.env["xb.jeweler.rate"]
        for repair in self:
            if repair.settlement_id:
                # Never move the price of something already being paid. The
                # value still has to be assigned, or the recompute leaves the
                # stored field without one.
                repair.jeweler_cost = repair.jeweler_cost
                continue
            repair.jeweler_cost = Rate._get_rate(
                repair.jeweler_id,
                repair.sale_order_line_id.product_id,
                repair.company_id or self.env.company,
            )

    def _compute_warranty_claim_count(self):
        data = self.env["repair.order"]._read_group(
            [("origin_repair_id", "in", self.ids)], ["origin_repair_id"], ["__count"]
        )
        counts = {origin.id: count for origin, count in data}
        for repair in self:
            repair.warranty_claim_count = counts.get(repair.id, 0)

    @api.depends("warranty_until", "state")
    def _compute_warranty_active(self):
        today = fields.Date.context_today(self)
        for repair in self:
            repair.warranty_active = bool(
                repair.warranty_until
                and repair.warranty_until >= today
                and repair.state in ("done", "delivered")
            )

    def _search_warranty_active(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise UserError(_("Unsupported search on the warranty."))
        today = fields.Date.context_today(self)
        active = [
            ("warranty_until", ">=", today),
            ("state", "in", ("done", "delivered")),
        ]
        if (operator == "=") == value:
            return active
        return ["!", "&"] + active

    @api.depends("weight_after_g", "jewelry_piece_id.weight_g")
    def _compute_weight_diff(self):
        for repair in self:
            before = repair.jewelry_piece_id.weight_g
            repair.weight_diff_g = (
                repair.weight_after_g - before if repair.weight_after_g and before else 0.0
            )

    @api.depends("jeweler_promised_date", "qc_date")
    def _compute_delay_days(self):
        for repair in self:
            if repair.jeweler_promised_date and repair.qc_date:
                repair.delay_days = (
                    repair.qc_date.date() - repair.jeweler_promised_date
                ).days
            else:
                repair.delay_days = 0

    @api.depends("xb_input_piece_ids.pure_metal_weight_g")
    def _compute_xb_input_pure_g(self):
        for repair in self:
            repair.xb_input_pure_g = sum(
                repair.xb_input_piece_ids.mapped("pure_metal_weight_g")
            )

    def _xb_photo_reference_piece(self):
        """The piece the intake checklist is about.

        For a repair that is the piece received. For a commission built out of
        the customer's own gold it is the first piece handed in, because that
        is what is physically on the counter and has to be documented. A
        commission from scratch has nothing to photograph at all.
        """
        self.ensure_one()
        if self.xb_service_type == "repair":
            return self.jewelry_piece_id
        return self.xb_input_piece_ids[:1] or self.jewelry_piece_id

    def _xb_applicable_photo_kinds(self, stage="intake", kinds=None):
        self.ensure_one()
        if kinds is None:
            kinds = self.env["xb.jewelry.photo.kind"].search([("stage", "=", stage)])
        else:
            kinds = kinds.filtered(lambda k: k.stage == stage)
        if stage == "design":
            # Only a commission has a design to show; a repair has nothing to
            # agree on beyond the piece itself.
            if self.xb_service_type == "repair":
                return kinds.browse()
            return kinds
        piece = self._xb_photo_reference_piece()
        if not piece:
            # Nothing physical was handed over, so there is nothing to record.
            return kinds.browse()
        return kinds.filtered(lambda k: self._photo_kind_applies(k, piece))

    @api.depends("photo_ids.kind_id", "xb_service_type",
                 "jewelry_piece_id.piece_kind", "jewelry_piece_id.has_diamond",
                 "jewelry_piece_id.has_laser_inscription",
                 "xb_input_piece_ids.piece_kind",
                 "xb_input_piece_ids.has_diamond")
    def _compute_missing_photo_kind_ids(self):
        # Read the checklist once, not once per order: this compute is what a
        # list of the whole workshop backlog triggers.
        all_kinds = self.env["xb.jewelry.photo.kind"].search(
            [("stage", "in", ("intake", "design"))]
        )
        for repair in self:
            company = repair.company_id or self.env.company
            applicable = (
                repair._xb_applicable_photo_kinds("intake", all_kinds)
                | repair._xb_applicable_photo_kinds("design", all_kinds)
            )
            taken = repair.photo_ids.kind_id
            required = applicable.filtered("required")
            repair.missing_photo_kind_ids = required - taken
            repair.xb_intake_missing_kind_ids = (
                company._xb_intake_required_kinds(applicable) - taken
            )

    @api.model
    def _photo_kind_applies(self, kind, piece):
        if kind.condition == "always":
            return True
        if not piece:
            return False
        if kind.condition == "ring":
            return piece.piece_kind == "ring"
        if kind.condition == "chain":
            return piece.piece_kind == "chain"
        if kind.condition == "diamond":
            return piece.has_diamond
        if kind.condition == "diamond_laser":
            # Photographing an inscription that does not exist wastes the
            # customer's time at the counter for nothing.
            return piece.has_diamond and piece.has_laser_inscription
        return True

    xb_board_alert = fields.Selection(
        [("late", "Late"), ("soon", "Due soon"), ("ok", "On time")],
        compute="_compute_xb_board_alert",
        store=True,
        string="Timeliness",
    )

    @api.depends("jeweler_promised_date", "state")
    def _compute_xb_board_alert(self):
        today = fields.Date.context_today(self)
        for repair in self:
            due = repair.jeweler_promised_date
            if not due or repair.state in ("delivered", "cancel", "done"):
                repair.xb_board_alert = "ok"
            elif due < today:
                repair.xb_board_alert = "late"
            elif (due - today).days <= 1:
                repair.xb_board_alert = "soon"
            else:
                repair.xb_board_alert = "ok"

    # --- Guards --------------------------------------------------------
    # Dragging a card on the board writes `state` straight to the database,
    # with none of the checks the buttons run. Rather than forbid dragging,
    # which is the whole point of the board, the same rules are enforced on
    # the write itself: our own actions have already checked, and say so.
    _XB_GUARDED_STATES = ("under_repair", "done", "delivered")

    def write(self, vals):
        state = vals.get("state")
        if state in self._XB_GUARDED_STATES and not self.env.context.get(
            "xb_skip_state_guard"
        ):
            for repair in self:
                if repair.state == state:
                    continue
                if state == "under_repair":
                    repair._check_ready_for_workshop()
                elif state == "done":
                    repair._check_quality_complete()
                elif state == "delivered":
                    repair._check_ready_for_delivery()
        return super().write(vals)

    def _check_ready_for_delivery(self):
        for repair in self:
            company = repair.company_id or self.env.company
            if company.xb_require_delivery_signature and not repair.delivery_signature:
                raise UserError(
                    _(
                        "The customer must sign the delivery of %(ref)s.",
                        ref=repair.name,
                    )
                )

    def _check_ready_for_workshop(self):
        for repair in self:
            company = repair.company_id or self.env.company
            if repair.state == "pending_auth":
                raise UserError(
                    _(
                        "%(ref)s is still waiting for the customer to authorize "
                        "the quote. Nothing goes to the workshop before that.",
                        ref=repair.name,
                    )
                )
            if repair.missing_photo_kind_ids:
                raise UserError(
                    _(
                        "Cannot hand %(ref)s to the workshop: the following "
                        "photos are still missing: %(kinds)s.",
                        ref=repair.name,
                        kinds=", ".join(repair.missing_photo_kind_ids.mapped("name")),
                    )
                )
            if company.xb_require_intake_signature and not repair.intake_signature:
                raise UserError(
                    _(
                        "Cannot hand %(ref)s to the workshop: the customer has "
                        "not signed the intake receipt.",
                        ref=repair.name,
                    )
                )
            if not repair.jeweler_id:
                raise UserError(
                    _("Assign a jeweler to %(ref)s first.", ref=repair.name)
                )

    def _check_quality_complete(self):
        for repair in self:
            checks = [
                repair.qc_weight_ok,
                repair.qc_stones_ok,
                repair.qc_size_ok,
                repair.qc_solder_ok,
                repair.qc_finish_ok,
            ]
            if repair.jewelry_piece_id.has_diamond:
                checks.append(repair.qc_tester_ok)
            if not all(checks):
                raise UserError(
                    _(
                        "The inspection checklist of %(ref)s is not complete. "
                        "Send the piece back for rework instead.",
                        ref=repair.name,
                    )
                )

    # --- Transitions ---------------------------------------------------
    def action_request_authorization(self):
        return self.write({"state": "pending_auth"})

    def action_authorize(self):
        self.filtered(lambda r: r.state == "pending_auth").write({"state": "draft"})
        return self._action_repair_confirm()

    def action_repair_start(self):
        # Going 'under repair' is, for a jeweller, the piece physically
        # leaving the counter. Nothing leaves without photos and a signature.
        self._check_ready_for_workshop()
        return super(
            RepairOrder, self.with_context(xb_skip_state_guard=True)
        ).action_repair_start()

    def action_receive_from_workshop(self):
        if self.filtered(lambda r: r.state not in ("under_repair", "rework")):
            raise UserError(_("Only pieces at the workshop can be received back."))
        return self.write({"state": "inspection"})

    def action_qc_pass(self):
        if self.filtered(lambda r: r.state != "inspection"):
            raise UserError(
                _("Only a piece under inspection can pass quality control.")
            )
        self._check_quality_complete()
        guarded = self.with_context(xb_skip_state_guard=True)
        guarded.write(
            {
                "qc_user_id": self.env.uid,
                "qc_date": fields.Datetime.now(),
                # action_repair_end() insists on 'under_repair'; we pass
                # through it so every native side effect still happens.
                "state": "under_repair",
            }
        )
        res = guarded.action_repair_end()
        for repair in self:
            days = (repair.company_id or self.env.company).xb_warranty_days
            if days:
                repair.warranty_until = fields.Date.add(
                    fields.Date.context_today(repair), days=days
                )
        return res

    def action_qc_fail(self):
        if self.filtered(lambda r: r.state != "inspection"):
            raise UserError(_("Only pieces under inspection can be sent to rework."))
        for repair in self:
            # Counted, not inferred from the state: once the rework is done the
            # order moves on and the state no longer remembers it happened.
            repair.rework_count += 1
        return self.write({"state": "rework"})

    def action_send_back_to_workshop(self):
        # It already passed every check the first time it left.
        return self.with_context(xb_skip_state_guard=True).write(
            {"state": "under_repair"}
        )

    def action_deliver(self):
        for repair in self:
            if repair.state != "done":
                raise UserError(
                    _("%(ref)s is not ready to be delivered.", ref=repair.name)
                )
        self._check_ready_for_delivery()
        return self.with_context(xb_skip_state_guard=True).write(
            {"state": "delivered"}
        )

    # --- Warranty ------------------------------------------------------
    def action_create_warranty_service(self):
        """Open a fresh service order to redo work that is still covered.

        A new order rather than reopening the old one: the piece leaves and
        comes back a second time, and both trips have to stay on the record,
        with their own photos, their own dispatch and their own signature.
        The customer is not charged, and neither is the jeweler paid twice
        unless the shop decides otherwise.
        """
        self.ensure_one()
        if not self.warranty_active:
            raise UserError(
                _(
                    "The warranty on %(ref)s is not in force: it either has no "
                    "warranty date, has expired, or the work is not finished.",
                    ref=self.name,
                )
            )
        claim = self.copy(
            {
                "origin_repair_id": self.id,
                "under_warranty": True,
                "state": "confirmed",
                "jeweler_id": self.jeweler_id.id,
                "jeweler_cost": 0.0,
                "warranty_until": False,
                "rework_count": 0,
                "jeweler_promised_date": False,
            }
        )
        # The piece is the same one: its file, its photos and its history all
        # carry over, which is the whole point of the warranty claim.
        claim.jewelry_piece_id = self.jewelry_piece_id.id
        claim.message_post(
            body=_(
                "Warranty claim on %(ref)s, covered until %(date)s.",
                ref=self.name,
                date=self.warranty_until,
            )
        )
        self.message_post(
            body=_("A warranty claim was opened: %(ref)s.", ref=claim.name)
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "repair.order",
            "res_id": claim.id,
            "view_mode": "form",
        }

    def action_view_warranty_claims(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "repair.order",
            "name": _("Warranty claims on %s", self.name),
            "view_mode": "list,form",
            "domain": [("origin_repair_id", "=", self.id)],
        }

    # --- Paying the jeweler --------------------------------------------
    def action_settle_now(self):
        """Settle these jobs on the spot, without waiting for the weekly cut.

        Some jewelers are paid when they hand the piece back and others on a
        period; both are the same document, so the shop never has to choose a
        payment method up front.
        """
        jewelers = self.mapped("jeweler_id")
        if len(jewelers) != 1:
            raise UserError(
                _("Settle jobs of one jeweler at a time.")
            )
        if self.filtered(lambda r: r.settlement_id):
            raise UserError(_("Some of these jobs are already on a settlement."))
        if self.filtered(lambda r: r.state not in ("done", "delivered")):
            raise UserError(_("Only finished jobs can be settled."))
        today = fields.Date.context_today(self)
        settlement = self.env["xb.jeweler.settlement"].create(
            {
                "jeweler_id": jewelers.id,
                "company_id": (self[0].company_id or self.env.company).id,
                "date_from": today,
                "date_to": today,
            }
        )
        self.settlement_id = settlement.id
        return {
            "type": "ir.actions.act_window",
            "res_model": "xb.jeweler.settlement",
            "res_id": settlement.id,
            "view_mode": "form",
        }
