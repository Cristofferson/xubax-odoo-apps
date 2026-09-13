# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS
# Original, clean-room implementation. ALL ERP logic (taxes, fiscal position,
# down payment / advance) is based exclusively on native Odoo
# (point_of_sale, pos_sale, sale) plus original design.
import logging

from markupsafe import Markup

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import SQL, email_normalize, email_normalize_all, float_compare, plaintext2html

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Marks (and classifies) a Sale Order created from the POS by this module.
    # Set by xb_create_order_from_pos. Drives: (a) suppressing the delivery on
    # confirmation, and (b) the mandatory layaway advance enforcement at the POS.
    xb_so_kind = fields.Selection(
        selection=[
            ("quotation", "Quotation"),
            ("order", "Order"),
            ("layaway", "Layaway"),
            ("order_layaway", "Order / Layaway"),
        ],
        string="POS document kind",
        copy=False,
        index=True,
    )
    # Goods not handed over yet. With pos.config.xb_list_until_delivered the POS list
    # of orders keeps a POS order / layaway while this is set, paid or not (Odoo's own
    # list drops anything without a balance, so a fully paid order vanished before it
    # could be delivered from the POS). Handed over = delivered by stock OR settled at
    # the POS: a settled line whose picking is still open (e.g. a serial number not
    # captured) was handed over at the counter and must not be offered again. Goods
    # only: pos_sale never marks a service as delivered, and down-payment and
    # section/note lines are not goods.
    xb_pending_delivery = fields.Boolean(
        string="Pending delivery",
        compute="_compute_xb_pending_delivery",
        search="_search_xb_pending_delivery",
    )

    @api.depends(
        "order_line.qty_delivered", "order_line.product_uom_qty",
        "order_line.pos_order_line_ids.qty", "order_line.pos_order_line_ids.order_id.state",
    )
    def _compute_xb_pending_delivery(self):
        for order in self:
            pending = False
            for line in order.order_line:
                if line.display_type or line.is_downpayment or line.product_id.type != "consu":
                    continue
                settled = sum(
                    line.sudo().pos_order_line_ids.filtered(
                        lambda pos_line: pos_line.order_id.state not in ("draft", "cancel")
                    ).mapped("qty")
                )
                if float_compare(
                    max(line.qty_delivered, settled), line.product_uom_qty,
                    precision_rounding=line.product_uom_id.rounding or 0.01,
                ) < 0:
                    pending = True
                    break
            order.xb_pending_delivery = pending

    def _search_xb_pending_delivery(self, operator, value):
        if operator != "in":
            return NotImplemented
        pending = SQL("""(
            SELECT l.order_id
              FROM sale_order_line l
              JOIN product_product pp ON pp.id = l.product_id
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
             WHERE l.display_type IS NULL
               AND COALESCE(l.is_downpayment, FALSE) = FALSE
               AND pt.type = 'consu'
               AND GREATEST(l.qty_delivered, COALESCE((
                       SELECT SUM(pl.qty)
                         FROM pos_order_line pl
                         JOIN pos_order po ON po.id = pl.order_id
                        WHERE pl.sale_order_line_id = l.id
                          AND po.state NOT IN ('draft', 'cancel')
                   ), 0)) < l.product_uom_qty
        )""")
        if True in value and False in value:
            return []
        if True in value:
            return [("id", "in", pending)]
        if False in value:
            return [("id", "not in", pending)]
        return [("id", "in", [])]

    @api.model
    def _load_pos_data_fields(self, config):
        # Expose to the POS frontend (recovery/down-payment flow + receipt):
        #  - xb_so_kind: layaway advance enforcement + receipt type header.
        #  - state: the receipt title is by STATE, not the frozen kind (a confirmed
        #    quotation prints PEDIDO). pos_sale already loads 'state', kept explicit.
        #  - access_token: build the SO portal URL (payment QR) for recovered SOs,
        #    where xbCreateOrderFromPos's stashed portal_url is absent (Phase 3 receipt).
        return super()._load_pos_data_fields(config) + ["xb_so_kind", "state", "access_token"]

    def action_confirm(self):
        # Phase 4: never create a delivery when confirming OUR POS-originated orders
        # (decision: all of them). pos_sale confirms the SO when the advance/payment
        # is collected; we inject the native `skip_procurement` context for our SOs
        # so action_confirm sets state to 'sale' without launching the stock rule
        # (sale_stock.sale.order.line._action_launch_stock_rule short-circuits on it).
        ours = self.filtered(
            lambda o: o.xb_so_kind and not self.env.context.get("skip_procurement")
        )
        if ours:
            super(SaleOrder, ours.with_context(skip_procurement=True)).action_confirm()
        rest = self - ours
        return super(SaleOrder, rest).action_confirm() if rest else True

    @api.depends('transaction_ids.state', 'transaction_ids.amount', 'order_line', 'amount_total',
                 'order_line.invoice_lines.parent_state', 'order_line.invoice_lines.price_total',
                 'order_line.pos_order_line_ids')
    def _compute_amount_unpaid(self):
        for sale_order in self:
            invoices = sale_order.order_line.invoice_lines.move_id.filtered(lambda invoice: invoice.state in ('draft', 'posted'))
            total_invoices_paid = sum(invoices.mapped('amount_total'))
            # XB FIX: el nativo suma el amount_total ENTERO de cada pos.order ligado, contando
            # productos sueltos vendidos en el mismo ticket como anticipo del SO. Sumamos solo el
            # subtotal de las LÍNEAS ligadas (igual que _compute_amount_to_invoice / _compute_amount_invoiced).
            # Las líneas de reembolso (qty < 0) deben RESTAR su magnitud: lo normal es que ya traigan
            # subtotal negativo, pero una línea de reembolso mal formada puede guardar el subtotal en
            # positivo (el signo queda solo en qty) -> forzamos la contribución negativa por magnitud
            # para que neutralice bien el anticipo. Solo usa campos nativos de point_of_sale/pos_sale.
            total_pos_orders_paid = sum(
                -abs(pos_line.price_subtotal_incl) if pos_line.qty < 0 else pos_line.price_subtotal_incl
                for pos_line in sale_order.order_line.pos_order_line_ids
            )
            sale_order.amount_unpaid = max(sale_order.amount_total - total_invoices_paid - total_pos_orders_paid - sale_order.amount_paid, 0.0)

    @api.model
    def xb_create_order_from_pos(self, payload):
        """Create a Quotation / Sale Order / Layaway from the POS.

        Coexists with the native ``pos_sale`` loader; it does NOT replace it.

        Expected ``payload`` keys (sent by the POS frontend in Phase 2):
            pos_config_id (int)         Point of Sale that originates the order.
            partner_id (int)            Customer.
            pricelist_id (int|False)    Pricelist used in the POS session.
            fiscal_position_id (int|False)
                                        Fiscal position already applied in POS.
            confirm (bool)              True  -> confirm the SO (Order/Layaway),
                                        False -> leave as draft Quotation.
            with_down_payment (bool)    The cashier intends to collect an advance
                                        (Layaway / optional advance). Used only to
                                        validate the down-payment product up front.
            lines (list[dict])          Cart lines, each:
                product_id (int), qty (float), price_unit (float, tax-EXCLUDED),
                discount (float, %), tax_ids (list[int], already POS-mapped),
                name (str, optional).
            amount_total (float)        Cart grand total (tax INCLUDED), used to
                                        validate parity to the cent.
            note (str, optional)        POS general customer note (plain text);
                                        written to sale.order.note when non-empty.
            internal_note (str, opt.)   POS internal note, already flattened to
                                        clean text on the client (getStrNotes);
                                        written to sale.order.internal_note when
                                        non-empty and the field exists.
            type (str, optional)        Chosen kind: "quotation" / "order" /
                                        "layaway" / "order_layaway". Used only for
                                        the chatter origin log label.

        Returns a dict with the created order id/name/amounts and the configured
        down-payment product, so the frontend can register the advance reusing the
        native ``pos_sale`` down-payment flow (Opción A).
        """
        config = self.env["pos.config"].browse(payload.get("pos_config_id")).exists()
        if not config:
            raise UserError(_("The Point of Sale configuration was not found."))

        # Server-side guard: the feature must be enabled for this POS. The button
        # is already hidden when the toggle is off, but we never trust the client.
        if not config.xb_enable_sale_order:
            raise UserError(_(
                "Creating quotations / orders / layaways is disabled for this "
                "Point of Sale."
            ))

        partner_id = payload.get("partner_id")
        if not partner_id:
            raise UserError(_("Select a customer before creating the order."))

        raw_lines = payload.get("lines") or []
        if not raw_lines:
            raise UserError(_("Add at least one product before creating the order."))

        # --- Anticipo (Opción A): reuse the native pos_sale down-payment product.
        # We do NOT collect the advance here: the POS order does, through the
        # native down-payment product (pos.config.down_payment_product_id), which
        # natively links the advance to this SO when the pos.order is paid.
        # Here we only verify it is configured and, if not, surface a clear
        # message to the cashier instead of failing later (adjustment for A).
        down_payment_product = config.down_payment_product_id
        if payload.get("with_down_payment") and not down_payment_product:
            raise UserError(_(
                "To register a layaway advance you must configure the "
                "down-payment product first:\n"
                "Point of Sale ▸ Settings ▸ this POS ▸ Down Payment Product."
            ))

        order_env = self.with_company(config.company_id).sudo()

        # --- Fiscalidad: force the EXACT POS taxes on every line for 1:1 parity.
        # The taxes in line['tax_ids'] are ALREADY mapped by the POS fiscal
        # position, so we set them explicitly and let the explicit value win over
        # the computed default. Passing them inside the same create() call is what
        # prevents the fiscal position from being applied a SECOND time on
        # already-mapped lines (adjustment "a").
        line_cmds = []
        for raw in raw_lines:
            vals = {
                "product_id": raw["product_id"],
                "product_uom_qty": raw.get("qty", 0.0),
                "price_unit": raw.get("price_unit", 0.0),
                "discount": raw.get("discount", 0.0),
                "tax_ids": [Command.set(raw.get("tax_ids") or [])],
            }
            if raw.get("name"):
                vals["name"] = raw["name"]
            # Per-line POS notes -> dedicated Text fields, each only when non-empty.
            # The POS currently sends only internal_note; the per-line customer note
            # is not captured (it is auto-filled with product/bin metadata in this
            # deployment), but we read both keys so the field is ready if it is
            # enabled later.
            line_customer_note = (raw.get("customer_note") or "").strip()
            if line_customer_note:
                vals["xb_customer_note"] = line_customer_note
            line_internal_note = (raw.get("internal_note") or "").strip()
            if line_internal_note:
                vals["xb_internal_note"] = line_internal_note
            line_cmds.append(Command.create(vals))

        order_vals = {
            "partner_id": partner_id,
            "order_line": line_cmds,
        }
        if payload.get("pricelist_id"):
            order_vals["pricelist_id"] = payload["pricelist_id"]
        # Kept on the header for traceability / downstream invoicing. Because the
        # line taxes above are explicit, setting it in the SAME create() does not
        # remap them now (it would only remap on a later recompute).
        if payload.get("fiscal_position_id"):
            order_vals["fiscal_position_id"] = payload["fiscal_position_id"]
        # Customer reference: carry the partner code (partner.ref, e.g. "A006461")
        # into the SO "Customer Reference" so it prints on the receipt and is visible
        # in the backend. Only when the partner actually has a ref.
        partner = self.env["res.partner"].browse(partner_id)
        if partner.ref:
            order_vals["client_order_ref"] = partner.ref
        # Phase 4: classify/mark this SO so we can suppress its delivery on confirm
        # and enforce the layaway advance at the POS.
        kind = payload.get("type")
        if kind:
            order_vals["xb_so_kind"] = kind
        # Document template per kind (configured per COMPANY): apply the company's
        # Quotation / Order / Layaway template so its validity (validity_date from
        # number_of_days), terms (note), and signature/payment requirements flow in
        # via the native sale_management computes. The PRODUCT LINES stay from the POS
        # cart -- the template's line-loading lives in @api.onchange handlers, which do
        # NOT fire on ORM create(). A POS-supplied note still wins: an explicit `note`
        # value (set below) is not recomputed. The combined "order_layaway" kind uses
        # the Order template.
        tmpl = {
            "quotation": config.company_id.xb_quotation_template_id,
            "order": config.company_id.xb_order_template_id,
            "layaway": config.company_id.xb_layaway_template_id,
            "order_layaway": config.company_id.xb_order_template_id,
        }.get(kind)
        if tmpl:
            order_vals["sale_order_template_id"] = tmpl.id
        # Map the POS order notes to their SO fields. Both sale.order.note and
        # sale.order.internal_note are Html fields here (internal_note comes from
        # sale_subscription), so plaintext2html keeps line breaks and escapes the
        # text. Each is set only when non-empty, so an empty note never overwrites
        # anything. internal_note is guarded by a field-existence check so the
        # module stays installable where sale_subscription is absent.
        note = (payload.get("note") or "").strip()
        if note:
            order_vals["note"] = plaintext2html(note)
        internal_note = (payload.get("internal_note") or "").strip()
        if internal_note and "internal_note" in self._fields:
            order_vals["internal_note"] = plaintext2html(internal_note)

        order = order_env.create(order_vals)

        # Defensive reconciliation: guarantee the stored line taxes are exactly
        # the POS ones, even if a compute tried to remap them. Writing an explicit
        # value here sticks (no dependency changes afterwards to trigger a remap).
        for line, raw in zip(order.order_line, raw_lines):
            wanted = set(raw.get("tax_ids") or [])
            if set(line.tax_ids.ids) != wanted:
                line.tax_ids = [Command.set(list(wanted))]

        # --- Fiscalidad (adjustment "b"): validate price with/without VAT by
        # comparing the grand total against the POS cart total, to the cent.
        # We validate on the DRAFT order and confirm only if it matches (no
        # confirm-then-revert). The UserError aborts the transaction (rolling back
        # the draft order) and acts as a guardrail for now.
        cart_total = payload.get("amount_total")
        if cart_total is not None:
            rounding = order.currency_id.rounding
            if float_compare(order.amount_total, cart_total, precision_rounding=rounding) != 0:
                raise UserError(_(
                    "The order total (%(so)s) does not match the POS cart total "
                    "(%(cart)s). Check whether prices are tax-included or "
                    "tax-excluded for this Point of Sale.",
                    so=order.amount_total, cart=cart_total,
                ))

        # All three types (Quotation / Order / Layaway) are created as a 'sent'
        # quotation. We do NOT confirm here: action_confirm() triggers premature
        # delivery ("Entrega 1"). Confirmation is deferred to the payment / advance
        # collection in Phase 4. action_quotation_sent only flips draft -> sent, so
        # the order is portal-visible and payable online right away.
        #
        # payload["confirm"] is intentionally NOT consumed at creation anymore; it is
        # kept as the Phase 4 hook (Order/Layaway will confirm when the advance/
        # payment is collected).
        order.action_quotation_sent()

        # Chatter origin legend: log an internal note (log note, mt_note) recording
        # that this SO was created from the POS, with the chosen kind, the POS name
        # and the cashier (self.env.user, since this orm.call runs as the cashier).
        type_labels = {
            "quotation": _("Quotation"),
            "order": _("Order"),
            "layaway": _("Layaway"),
            "order_layaway": _("Order / Layaway"),
        }
        type_label = type_labels.get(payload.get("type")) or _("Order")
        body = Markup(
            "<p>🧾 <b>%(title)s</b></p>"
            "<ul>"
            "<li><b>%(type_lbl)s</b> %(type_val)s</li>"
            "<li><b>%(pos_lbl)s</b> %(pos_val)s</li>"
            "<li><b>%(cashier_lbl)s</b> %(cashier_val)s</li>"
            "</ul>"
        ) % {
            "title": _("Created from the Point of Sale"),
            "type_lbl": _("Type:"),
            "type_val": type_label,
            "pos_lbl": _("Point of Sale:"),
            "pos_val": config.name,
            "cashier_lbl": _("Cashier:"),
            "cashier_val": self.env.user.name,
        }
        order.message_post(body=body, message_type="comment", subtype_xmlid="mail.mt_note")

        # Portal: build the ABSOLUTE URL so the POS receipt can show the online link
        # + QR (review / pay / settle online). get_portal_url() ensures the access
        # token itself (it calls _portal_ensure_token internally), which also sets it
        # on the SO — the receipt's fallback path loads that token to build the QR.
        portal_url = order.get_base_url() + order.get_portal_url()

        return {
            "sale_order_id": order.id,
            "name": order.name,
            "state": order.state,
            "amount_untaxed": order.amount_untaxed,
            "amount_tax": order.amount_tax,
            "amount_total": order.amount_total,
            "amount_unpaid": order.amount_unpaid,
            "portal_url": portal_url,
            "partner_ref": partner.ref or "",
            "down_payment_product_id": down_payment_product.id or False,
        }

    # ------------------------------------------------------------------
    # Quotation delivery: printed (POS side), WhatsApp, email
    # ------------------------------------------------------------------
    def xb_send_order_from_pos(self, options):
        """Send a quotation created at the POS to its customer, by WhatsApp and/or email.

        The POS calls it right after the quotation is created and the cart is gone,
        so a slow send never holds the cashier. What travels is the ticket the POS
        prints, drawn to an image by the POS itself (``ticket_image``), never the
        formal quotation PDF: the customer gets exactly what the shop hands over on
        paper.

        Each channel runs in its own savepoint and reports back instead of raising:
        a WhatsApp failure never cancels the email, and neither undoes the quotation,
        which is already committed.

        ``options`` keys:
            pos_config_id (int)     Point of Sale that sends it.
            ticket_image (str)      The printed ticket, base64 JPEG.
            phone (str|False)       WhatsApp number, when WhatsApp was chosen.
            email (str|False)       Email address, when email was chosen.

        Returns ``{"whatsapp": {...}, "email": {...}}`` for the channels asked, each
        ``{"ok": bool, "to": str, "error": str}``.
        """
        self.ensure_one()
        if not self.env.user.has_group("point_of_sale.group_pos_user"):
            raise AccessError(_("Only Point of Sale users can send quotations from the POS."))
        # The cashier may lack Sales rights (the POS creates these orders in sudo as
        # well); what keeps this safe is that it only ever sends documents this
        # module created from the POS.
        order = self.sudo()
        if not order.xb_so_kind:
            raise UserError(_("This document was not created from the Point of Sale."))
        config = self.env["pos.config"].browse(options.get("pos_config_id")).exists()
        if not config:
            raise UserError(_("The Point of Sale configuration was not found."))
        ticket_image = options.get("ticket_image")
        if not ticket_image:
            raise UserError(_("The ticket image is missing, so nothing was sent."))
        # One attachment for every channel, created outside their savepoints so a
        # failed channel cannot take it away from the other one.
        ticket = self.env["ir.attachment"].sudo().create({
            "name": "%s.jpg" % order.name,
            "type": "binary",
            "datas": ticket_image,
            "res_model": order._name,
            "res_id": order.id,
            "mimetype": "image/jpeg",
        })
        results = {}
        phone = (options.get("phone") or "").strip()
        if phone:
            results["whatsapp"] = order._xb_pos_deliver(
                order._xb_pos_send_whatsapp, phone, config, ticket
            )
        email = (options.get("email") or "").strip()
        if email:
            results["email"] = order._xb_pos_deliver(
                order._xb_pos_send_email, email, config, ticket
            )
        return results

    def _xb_pos_deliver(self, sender, destination, config, ticket):
        """Run one channel's ``sender`` in a savepoint; report instead of raising."""
        try:
            with self.env.cr.savepoint():
                sent_to = sender(destination, config, ticket)
        except UserError as error:
            return {"ok": False, "to": destination, "error": str(error)}
        except Exception as error:
            _logger.exception("Sending %s to %s from the POS failed", self.name, destination)
            return {"ok": False, "to": destination, "error": str(error)}
        return {"ok": True, "to": sent_to or destination}

    def _xb_pos_send_email(self, email, config, ticket):
        normalized = email_normalize(email)
        if not normalized:
            raise UserError(_("%s is not a valid email address.", email))
        template = self.env.ref(
            "xb_sale_order_from_pos.mail_template_pos_quotation_ticket", raise_if_not_found=False
        )
        if not template:
            raise UserError(_("The email template for POS quotations was deleted."))
        partner = self.partner_id
        # Fill the customer's email only when it has none; never overwrite the one
        # the shop keeps. A different address is used for this send only.
        if not partner.email:
            partner.email = email
        layout = "mail.mail_notification_layout_with_responsible_signature"
        if normalized in email_normalize_all(partner.email):
            # To the customer: the native notification path, so the chatter keeps the
            # email with its ticket, like any quotation sent from Sales.
            self.with_context(force_send=True).message_post_with_source(
                template,
                email_layout_xmlid=layout,
                subtype_xmlid="mail.mt_comment",
                attachment_ids=[ticket.id],
            )
        else:
            # A one-off address: same email and ticket, only to it.
            mail_id = template.send_mail(
                self.id,
                force_send=True,
                email_layout_xmlid=layout,
                email_values={
                    "email_to": email,
                    "recipient_ids": [],
                    "attachment_ids": [Command.link(ticket.id)],
                },
            )
            # force_send already tried it: a sent mail is gone (auto_delete), a failed
            # one stays in "exception" with its reason.
            mail = self.env["mail.mail"].browse(mail_id).exists()
            if mail and mail.state == "exception":
                raise UserError(mail.failure_reason or _("The email could not be sent."))
            self.message_post(
                body=_("Quotation ticket sent by email to %s.", email),
                attachment_ids=[ticket.id],
                subtype_xmlid="mail.mt_note",
            )
        return email

    def _xb_pos_send_whatsapp(self, phone, config, ticket):
        # WhatsApp comes with the optional add-on xb_sale_order_from_pos_whatsapp (it
        # needs Odoo Enterprise's WhatsApp). Without it the POS never offers this
        # channel, so only an outdated POS screen can land here.
        raise UserError(_("WhatsApp is not available in this database."))
