# -*- coding: utf-8 -*-
"""Attributing a ticket to a visit — and, sometimes, to a name.

Two separate things live here, and the distance between them is the point.

**Attribution (anonymous).** Tie the ticket to the pseudonymous visit that
produced it. That answers questions no aggregate can: does the profile that
stops at the window actually buy, does a group spend more than a lone shopper,
is the customer who comes back every fortnight worth more than the one who
comes once. None of it needs anyone's name.

**Identification (named).** When the customer *hands over their details at the
till* — which some pieces already require for the invoice — the face signature
they arrived with can be attached to that ``res.partner``. From then on the shop
recognises them at the door and can greet them properly.

The second is a different order of thing from the first, so it is gated
separately: off unless the store turns it on, restricted to the moment a
customer volunteered their identity to a person, and every later *read* of it
audited (task 984, point 6). A store that only wants the analytics never has to
touch it.

Group tickets
-------------
A ticket belongs to the **purchase unit** frozen at the door, not to whichever
individual paid: a family's spend is the family's. Inside that unit the face
seen at the till is the payer, which is who the identification attaches to.
"""
import logging

from odoo import api, fields, models, _

from .analitix_crypto import decode_embedding
from .analitix_job import register_handler

_logger = logging.getLogger(__name__)


class AnalitixSaleMatch(models.Model):
    _name = "analitix.sale.match"
    _description = "Analitix Visit ↔ Ticket"
    _order = "matched_at desc, id desc"
    _rec_name = "pos_order_id"

    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)
    visitor_id = fields.Many2one(
        "analitix.visitor", string="Visit", index=True, ondelete="cascade")
    visit_group_id = fields.Many2one(
        "analitix.visit.group", string="Purchase Unit", index=True,
        ondelete="set null",
        help="The unit the ticket belongs to. A family's spend is the family's, "
             "not the individual's who happened to hold the card.")
    pos_order_id = fields.Many2one(
        "pos.order", string="Ticket", required=True, index=True,
        ondelete="cascade")

    matched_at = fields.Datetime(
        string="Matched", required=True, index=True,
        default=lambda self: fields.Datetime.now())
    method = fields.Selection(
        selection=[
            ("face", "Face at the till"),
            ("group", "Through the purchase unit"),
            ("partner", "Through the customer record"),
            ("manual", "Set by hand"),
        ],
        string="How", required=True, default="face", index=True)
    confidence = fields.Float(
        string="Confidence", digits=(3, 3),
        help="Similarity behind a face match. Kept so a store seeing odd "
             "attributions can re-tune its threshold against real numbers.")

    _order_uniq = models.Constraint(
        "unique(pos_order_id)",
        "This ticket is already attributed to a visit.")
    _store_matched_idx = models.Index("(store_id, matched_at DESC)")

    # ------------------------------------------------------------------
    @api.model
    def _run_match_checkout(self, job):
        """Resolve a till face to the visit that arrived with it."""
        payload = job._payload()
        order = self.env["pos.order"].sudo().browse(
            payload.get("order_id") or 0).exists()
        store = self.env["analitix.store"].sudo().browse(
            payload.get("store_id") or 0).exists()
        if not order or not store:
            return True

        vector = decode_embedding(payload.get("embedding"))
        visitor = self.env["analitix.visitor"]
        confidence = 0.0
        method = "group"

        if vector and store.checkout_match_enabled:
            Signature = self.env["analitix.face.signature"].sudo()
            crypto = self.env["analitix.crypto"]
            probe = crypto.normalize(vector)
            best_row, best_score = None, 0.0
            for row, known in Signature._candidates(store, "buffalo_l"):
                if len(known) != len(probe):
                    continue
                score = sum(a * b for a, b in zip(probe, known))
                if score > best_score:
                    best_row, best_score = row, score
            if best_row is not None and best_score >= store.checkout_match_threshold:
                visitor = best_row.visitor_ids[:1]
                confidence = best_score
                method = "face"

        if not visitor:
            return True

        match = self._attach(store, order, visitor, method, confidence)

        # Graduating an anonymous visitor into an identified customer is a
        # separate, gated step — see _maybe_identify for why.
        if match and order.partner_id:
            self._maybe_identify(store, visitor, order.partner_id)
        return True

    @api.model
    def _attach(self, store, order, visitor, method, confidence=0.0):
        """Create the bridge, unless this ticket already has one."""
        if self.sudo().search_count([("pos_order_id", "=", order.id)]):
            return self.browse()
        return self.sudo().create({
            "store_id": store.id,
            "visitor_id": visitor.id,
            "visit_group_id": visitor.visit_group_id.id,
            "pos_order_id": order.id,
            "method": method,
            "confidence": confidence,
        })

    @api.model
    def _maybe_identify(self, store, visitor, partner):
        """Attach the visit's face signature to a real customer record.

        Three gates, all of which must be open:

        1. the store switched identification on — it is off by default, because
           a shop that only bought the analytics should never acquire a
           biometric customer index by accident;
        2. there is a ``res.partner``, which in practice means the customer
           gave their details to a person at the till;
        3. the reading passed liveness if the store requires it — this is one
           of the consequential decisions task 984 names, since a persistent
           identified signature is exactly what a photograph should not be able
           to create.
        """
        if not store.identify_customers or not partner or not visitor:
            return False
        signature = visitor.signature_id
        if not signature or signature.partner_id:
            return False
        if store.require_liveness and signature.liveness_score < store.liveness_min_score:
            _logger.info(
                "Analitix: not identifying a customer on a low-liveness "
                "reading at store %s.", store.display_name)
            return False

        signature.sudo().write({
            "partner_id": partner.id,
            "identified": True,
            # An identified signature outlives the anonymous retention window —
            # that is the point of it — but not forever. The store sets how
            # long, and the same expiry cron enforces it.
            "expires_at": fields.Datetime.add(
                fields.Datetime.now(), days=store.identified_ttl_days),
        })
        self.env["analitix.audit.log"].sudo().log(
            action="elevated", model="analitix.face.signature",
            res_id=signature.id, store=store,
            note=_("Face signature linked to customer %s", partner.display_name))
        return True


register_handler("match_checkout", "analitix.sale.match", "_run_match_checkout")


class PosOrder(models.Model):
    """Hook the till into the pipeline.

    Everything here is queued rather than done inline. A cashier closing a sale
    must never wait on a face comparison, and a failure in this path must never
    be able to block a payment — the customer is standing at the counter.
    """
    _inherit = "pos.order"

    analitix_match_id = fields.Many2one(
        "analitix.sale.match", string="Analitix Visit", ondelete="set null",
        copy=False, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        try:
            orders._analitix_enqueue_match()
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Analitix: could not queue checkout matching; the sale is "
                "unaffected.")
        return orders

    def _analitix_enqueue_match(self):
        """Queue attribution for each order that belongs to a tracked store."""
        Store = self.env["analitix.store"].sudo()
        Job = self.env["analitix.job"].sudo()
        for order in self:
            store = Store._for_pos_config(order.config_id)
            if not store or not store.checkout_match_enabled:
                continue
            # The face, if a till camera sent one, arrives through the ingest
            # API and is parked in context by the POS bridge; absent it, the
            # match falls back to the purchase unit, which is why a store with
            # no till camera still gets group-level attribution.
            embedding = self.env.context.get("analitix_checkout_embedding")
            Job.enqueue("match_checkout", {
                "order_id": order.id,
                "store_id": store.id,
                "embedding": embedding,
            }, store=store, priority=3)
        return True
