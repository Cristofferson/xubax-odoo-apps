from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


class RepairOrder(models.Model):
    """Endpoints the Point of Sale calls.

    Everything is built server side on purpose: the native repair order needs
    an operation type and four locations that the cashier has no business
    knowing about, and building the record in the browser would mean shipping
    all of that to the front end.
    """

    _inherit = "repair.order"

    def _xb_pos_read(self):
        """Compact payload for the POS screens."""
        return [
            {
                "id": repair.id,
                "name": repair.name,
                "state": repair.state,
                "partner_id": repair.partner_id.id,
                "partner_name": repair.partner_id.display_name,
                "piece_id": repair.jewelry_piece_id.id,
                "piece_name": repair.jewelry_piece_id.name,
                "piece_description": repair.jewelry_piece_id.description,
                "piece_type": repair.jewelry_piece_id.piece_type_id.display_name,
                "weight_g": repair.jewelry_piece_id.weight_g,
                "metal": repair.jewelry_piece_id.metal_value_id.display_name,
                "jeweler_name": repair.jeweler_id.display_name,
                "promised_date": repair.jeweler_promised_date
                and fields.Date.to_string(repair.jeweler_promised_date),
                "sale_order_name": repair.sale_order_id.name,
                # A signature is not a payment. The counter has to be able to
                # see, before handing the piece back, whether anything is
                # still owed on it.
                "balance_due": repair.sale_order_id and repair._xb_balance_due() or 0.0,
                "balance_due_label": repair.sale_order_id and formatLang(
                    self.env,
                    repair._xb_balance_due(),
                    currency_obj=repair._xb_balance_currency(),
                ) or "",
                "missing_photos": repair.missing_photo_kind_ids.mapped("name"),
                "has_intake_signature": bool(repair.intake_signature),
                "has_delivery_signature": bool(repair.delivery_signature),
                "photo_ids": repair.photo_ids.ids,
                # Why a piece cannot leave for the workshop, worked out on the
                # server so the counter reads a reason instead of a traceback.
                "dispatch_blocker": repair._xb_pos_dispatch_blocker(),
            }
            for repair in self
        ]

    def _xb_pos_dispatch_blocker(self):
        """Human readable reason this piece cannot go to the workshop yet."""
        self.ensure_one()
        company = self.company_id or self.env.company
        if self.state == "pending_auth":
            return _("The customer has not authorized the quote yet.")
        if self.state not in ("draft", "confirmed"):
            return _("This piece is not at the counter.")
        if self.missing_photo_kind_ids:
            return _(
                "Missing photos: %(kinds)s",
                kinds=", ".join(self.missing_photo_kind_ids.mapped("name")),
            )
        if company.xb_require_intake_signature and not self.intake_signature:
            return _("The customer has not signed the intake receipt.")
        return False

    @api.model
    def _xb_pos_company(self, pos_config_id=None):
        """The company the register belongs to, not the user's default.

        In a group with several companies, a cashier's default company is not
        necessarily the one the till trades under. Getting this wrong makes
        Odoo refuse to link the service order to the sale order it created,
        which is exactly the pairing this module exists to make.
        """
        if pos_config_id:
            config = self.env["pos.config"].browse(int(pos_config_id)).exists()
            if config.company_id:
                return config.company_id
        return self.env.company

    @api.model
    def xb_pos_settings(self, pos_config_id=None):
        """What the counter screens need to know before drawing anything.

        Sent in one call instead of preloading it with the session: it is a
        handful of values, and the shop can change them without every register
        having to be closed and reopened.
        """
        company = self._xb_pos_company(pos_config_id)
        main = company.xb_intake_main_photo_kind_id
        return {
            "require_intake_signature": company.xb_require_intake_signature,
            "require_dispatch_signature": company.xb_require_dispatch_signature,
            "require_delivery_signature": company.xb_require_delivery_signature,
            "intake_terms": company.xb_intake_terms or "",
            "delivery_terms": company.xb_delivery_terms or "",
            # How much the customer has to stand there for. The workshop guard
            # is unaffected: the photos are still owed, just not right now.
            "intake_photo_policy": company.xb_intake_photo_policy,
            "intake_main_photo_code": main.code or "",
            # Handing pieces to a jeweler is a workshop right, not a cashier
            # one. Asked here so the button is simply absent rather than
            # throwing an access error in the customer's face.
            "can_dispatch": self.env.user.has_group(
                "xb_jewelry_service.group_jewelry_workshop"
            ),
            # Whether an unpaid balance stops the hand-over, only warns, or is
            # nobody's business at the counter.
            "delivery_balance_policy": company.xb_delivery_balance_policy,
        }

    @api.model
    def xb_pos_search(self, query=None, only_ready=False, limit=40, mode=None):
        domain = [
            ("state", "not in", ("cancel",)),
            ("jewelry_piece_id", "!=", False),
        ]
        if mode == "dispatch":
            # Only pieces still at the counter can be handed over.
            domain.append(("state", "in", ("draft", "confirmed")))
            domain.append(("dispatch_id", "=", False))
        elif only_ready:
            domain.append(("state", "=", "done"))
        else:
            domain.append(("state", "!=", "delivered"))
        if query:
            domain += [
                "|",
                "|",
                "|",
                ("name", "ilike", query),
                ("partner_id.name", "ilike", query),
                ("jewelry_piece_id.name", "ilike", query),
                ("jewelry_piece_id.description", "ilike", query),
            ]
        return self.search(domain, limit=limit, order="id desc")._xb_pos_read()

    @api.model
    def xb_pos_receive_piece(self, vals):
        """Create the piece file and its service order in one go.

        Called the moment the piece is physically handed over, whether or not
        the customer pays anything: the shop is holding someone else's gold and
        that cannot wait for a payment to be recorded.
        """
        partner_id = vals.get("partner_id")
        if not partner_id:
            raise UserError(_("Select the customer first."))

        # The register's company, so the piece, the service order and the sale
        # order all belong to the same one.
        company = self._xb_pos_company(
            vals.get("pos_config_id")
            or (vals.get("sale_payload") or {}).get("pos_config_id")
        )
        self = self.with_company(company)
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", company.id)], limit=1
        )
        if not warehouse.repair_type_id:
            raise UserError(
                _("This warehouse has no repair operation type configured.")
            )

        service_type = vals.get("service_type") or "repair"
        Piece = self.env["xb.jewelry.piece"]

        def build_piece(data, default_desc):
            return Piece.create(
                {
                    "partner_id": partner_id,
                    "description": data.get("description") or default_desc,
                    "piece_type_id": data.get("piece_type_id") or False,
                    "metal_value_id": data.get("metal_value_id") or False,
                    "weight_g": data.get("weight_g") or 0.0,
                    "size_value_id": data.get("size_value_id") or False,
                    "length_cm": data.get("length_cm") or 0.0,
                    "stone_count": data.get("stone_count") or 0,
                    "has_diamond": data.get("has_diamond") or False,
                    "has_laser_inscription": data.get("has_laser_inscription") or False,
                    "diamond_tester": data.get("diamond_tester") or False,
                    "laser_inscription": data.get("laser_inscription") or False,
                    "company_id": company.id,
                }
            )

        # For a repair the piece described IS the one received. For a
        # commission it is the one to be made, and what the customer physically
        # hands over is their old gold, filed as pieces of its own so the
        # custody trail is the same one a repair gets.
        piece = build_piece(vals, _("Piece"))
        input_pieces = Piece.browse()
        for raw in vals.get("input_pieces") or []:
            input_pieces |= build_piece(raw, _("Customer's gold"))

        repair = self.create(
            {
                "partner_id": partner_id,
                "xb_service_type": service_type,
                "jewelry_piece_id": piece.id,
                "xb_input_piece_ids": [(6, 0, input_pieces.ids)],
                "xb_spec": vals.get("spec") or False,
                "picking_type_id": warehouse.repair_type_id.id,
                "company_id": company.id,
                "xb_customer_request": vals.get("note") or False,
                "sale_order_id": vals.get("sale_order_id") or False,
                "sale_order_line_id": vals.get("sale_order_line_id") or False,
                "state": "confirmed",
            }
        )

        for photo in vals.get("photos") or []:
            self.env["xb.jewelry.photo"].create(
                {
                    "kind_id": photo["kind_id"],
                    "repair_id": repair.id,
                    "piece_id": piece.id,
                    "image": photo["image"],
                }
            )

        if vals.get("signature"):
            repair.write(
                {
                    "intake_signature": vals["signature"],
                    "intake_signed_by": vals.get("signed_by")
                    or repair.partner_id.name,
                    "intake_signed_on": fields.Datetime.now(),
                }
            )
        elif company.xb_require_intake_signature:
            raise UserError(
                _("The customer has to sign the intake receipt before the "
                  "shop takes the piece.")
            )

        # One pass at the counter: the same click that takes the piece in also
        # raises the order that will be charged, so the cashier never has to
        # remember to do the commercial half separately.
        #
        # Unless the cashier already raised it, with the "Create Order" button
        # of the commercial bridge. Both buttons hand the SAME cart to the SAME
        # backend method, and neither used to ask whether the other had already
        # been pressed: two sale orders for one ring, which is precisely the
        # confusion this app exists to prevent. When the register tells us
        # which order it is already carrying, the job is hung off that one and
        # nothing new is created.
        sale_info = False
        existing = self.env["sale.order"].browse(vals.get("sale_order_id") or []).exists()
        if existing:
            repair._xb_pos_bind_sale_order(existing)
            sale_info = {
                "sale_order_id": existing.id,
                "name": existing.name,
                "reused": True,
            }
        elif vals.get("sale_payload"):
            sale_info = repair._xb_pos_attach_sale_order(vals["sale_payload"])

        # Soft hook: the WhatsApp bridge is a separate, optional module, so the
        # call is made only when it is installed.
        if hasattr(repair, "xb_pos_receive_piece_hook"):
            repair.xb_pos_receive_piece_hook()

        payload = repair._xb_pos_read()[0]
        # Handed back so the register can remember the order on its cart and
        # stop offering to create a second one.
        payload["sale_order"] = sale_info or False
        return payload

    def _xb_pos_attach_sale_order(self, payload):
        """Raise the sale order for this service and hang the job off its line.

        Delegates to xb_sale_order_from_pos, which already knows how to build a
        quotation, an order or a layaway with the POS taxes to the cent. That
        module stays the authority on the commercial side; this one only asks
        it for the document and remembers which line the piece belongs to.
        """
        self.ensure_one()
        SaleOrder = self.env["sale.order"]
        if not hasattr(SaleOrder, "xb_create_order_from_pos"):
            # The commercial bridge is not installed. The piece is still safely
            # in custody, which is what actually matters here.
            self.message_post(
                body=_("No sale order was raised: the POS order bridge is not "
                       "installed.")
            )
            return False
        try:
            result = SaleOrder.xb_create_order_from_pos(payload)
        except Exception as error:  # noqa: BLE001
            # Never lose the custody record over a commercial failure: the gold
            # is already behind the counter.
            self.message_post(
                body=_("The piece was taken in, but the order could not be "
                       "raised: %(err)s", err=str(error)[:200])
            )
            return False
        order = SaleOrder.browse(result.get("sale_order_id")).exists()
        if not order:
            return False
        self._xb_pos_bind_sale_order(order)
        return result

    def _xb_pos_bind_sale_order(self, order):
        """Hang this job off the right line of an order that already exists.

        Used both by the order this module raises itself and by the one the
        cashier raised a minute earlier with "Create Order": from here on the
        two paths are the same, and only one document ever exists per piece.
        """
        self.ensure_one()
        if order.company_id != self.company_id:
            # Odoo refuses to cross companies, and it is right to. Say so
            # plainly instead of letting the counter meet a traceback: the
            # piece is already in custody either way.
            self.message_post(
                body=_(
                    "Order %(order)s belongs to %(theirs)s while this service "
                    "belongs to %(ours)s, so they were left unlinked. Check "
                    "which company the register trades under.",
                    order=order.name,
                    theirs=order.company_id.display_name,
                    ours=self.company_id.display_name,
                )
            )
            return False
        # Prefer the line that IS the repair service; fall back to any service,
        # then to the first line, so the job is never left dangling.
        lines = order.order_line.filtered(lambda l: not l.display_type)
        line = lines.filtered(
            lambda l: l.product_id.product_tmpl_id.service_tracking == "repair"
        )[:1]
        if not line:
            line = lines.filtered(lambda l: l.product_id.type == "service")[:1]
        if not line:
            line = lines[:1]
        self.write({
            "sale_order_id": order.id,
            "sale_order_line_id": line.id or False,
        })
        if line:
            self._xb_drop_duplicate_repair(line)
        return order

    def _xb_drop_duplicate_repair(self, line):
        """Remove the empty repair order Odoo raises on its own.

        When the service product is set up with service_tracking = 'repair',
        confirming the sale order makes Odoo create one repair order per line.
        Its own guard skips lines that already have one, but the order is
        confirmed inside the commercial bridge, before we get the chance to
        link ours. What is left behind is an empty shell with no piece, and
        two orders for one ring is exactly the confusion this app exists to
        avoid.
        """
        self.ensure_one()
        shells = self.search(
            [
                ("id", "!=", self.id),
                ("sale_order_line_id", "=", line.id),
                ("jewelry_piece_id", "=", False),
                ("state", "in", ("draft", "confirmed")),
            ]
        )
        # Only ever discard what is genuinely empty: no photos, no signature,
        # nothing anybody typed.
        shells = shells.filtered(
            lambda r: not r.photo_ids and not r.intake_signature and not r.move_ids
        )
        if shells:
            shells.sudo().unlink()
        return shells

    @api.model
    def xb_pos_deliver(self, repair_id, signature=None, signed_by=None):
        repair = self.browse(repair_id)
        company = repair.company_id or self.env.company
        if not signature and company.xb_require_delivery_signature:
            raise UserError(
                _("The customer has to sign for the piece before it is handed "
                  "back.")
            )
        if signature:
            repair.write(
                {
                    "delivery_signature": signature,
                    "delivery_signed_by": signed_by or repair.partner_id.name,
                    "delivery_signed_on": fields.Datetime.now(),
                }
            )
        repair.action_deliver()
        return repair._xb_pos_read()[0]

    @api.model
    def xb_pos_piece_types(self):
        """El árbol de categorías de la tienda, ya marcadas como joyería."""
        cats = self.env["product.category"].search(
            [("xb_jewelry_kind", "!=", False)], order="complete_name")
        return [{"id": c.id, "name": c.complete_name, "kind": c.xb_jewelry_kind}
                for c in cats]

    @api.model
    def xb_pos_sizes(self, pos_config_id=None):
        attribute = self._xb_pos_company(pos_config_id).xb_size_attribute_id
        if not attribute:
            return []
        return [{"id": v.id, "name": v.name} for v in
                self.env["product.attribute.value"].search(
                    [("attribute_id", "=", attribute.id)])]

    @api.model
    def xb_pos_metal_values(self, pos_config_id=None):
        attribute = self._xb_pos_company(pos_config_id).xb_metal_attribute_id
        if not attribute:
            return []
        values = self.env["product.attribute.value"].search(
            [("attribute_id", "=", attribute.id)]
        )
        return [{"id": v.id, "name": v.name} for v in values]

    @api.model
    def xb_pos_dispatch(self, repair_ids, jeweler_id, signature=None,
                        signed_by=None, promised_date=None, pos_config_id=None):
        """Hand pieces to a jeweler from the counter."""
        if not self.env.user.has_group("xb_jewelry_service.group_jewelry_workshop"):
            raise UserError(
                _("Handing pieces to a jeweler is done by the workshop. Ask "
                  "someone with that access to do it.")
            )
        if not repair_ids:
            raise UserError(_("Pick at least one piece to hand over."))
        if not jeweler_id:
            raise UserError(_("Pick the jeweler taking the pieces."))
        company = self._xb_pos_company(pos_config_id)
        if company.xb_require_dispatch_signature and not signature:
            raise UserError(_("The jeweler has to sign for the pieces."))
        dispatch = self.env["xb.jewelry.dispatch"].with_company(company).create(
            {
                "jeweler_id": jeweler_id,
                "company_id": company.id,
                "promised_date": promised_date or False,
                "repair_ids": [(6, 0, repair_ids)],
                "signature": signature or False,
                "signed_by": signed_by or False,
                "signed_on": fields.Datetime.now() if signature else False,
            }
        )
        dispatch.action_dispatch()
        return {"id": dispatch.id, "name": dispatch.name}

    @api.model
    def xb_pos_photo_link(self, repair_id):
        """QR the counter shows so the photos can be taken with a phone."""
        return self.browse(repair_id).xb_generate_photo_link()

    @api.model
    def xb_pos_jewelers(self, pos_config_id=None):
        jewelers = self.env["res.partner"].search([("is_jeweler", "=", True)])
        return [{"id": j.id, "name": j.display_name} for j in jewelers]
