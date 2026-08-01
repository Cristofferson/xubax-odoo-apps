# -*- coding: utf-8 -*-
"""The anonymous face signature: how one person stays one person.

This is what turns a pile of crossings into visits.  Without it a customer who
walks in the north door, leaves through the south door and comes back twenty
minutes later is four visitors and the store's conversion rate is a quarter of
the truth.

It is deliberately *anonymous and short-lived*:

* the vector is encrypted at rest and no image exists anywhere in the pipeline;
* every signature carries an expiry, set per store, and a cron deletes them —
  retention is a configured number of hours, not "forever by omission";
* nothing here is tied to a name. Phase 3 adds the optional bridge to a
  ``res.partner``, and that is a separate, deliberate step for a customer who
  handed over their details at the till.

Scope of matching, and why it is what it is
-------------------------------------------
Matching is always **within one store**. A person recognised in branch A is not
silently joined to their visit in branch B: that is a decision about the reach
of a customer's data, and task 983 puts it behind the highest corporate role
for good reason. Here it is not even possible.

Within the store, re-identification across doors happens only when the store
*has* more than one door — which is read from the configuration, never assumed.
A single-door boutique gets re-entry detection through the same door and
nothing else, because there is nothing else to correlate.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models, _

from .analitix_job import register_handler

_logger = logging.getLogger(__name__)


class AnalitixFaceSignature(models.Model):
    _name = "analitix.face.signature"
    _description = "Analitix Anonymous Face Signature"
    # The audit mixin logs *reads*, not only writes (task 984, point 6). Once a
    # signature can carry a customer's name, going through this list is itself
    # an act worth recording — Odoo's chatter would only ever show who changed
    # something, never who looked.
    _inherit = ["analitix.audited.mixin"]
    _audit_action = "read_sensitive"
    _order = "last_seen desc, id desc"
    _rec_name = "reference"

    reference = fields.Char(
        string="Reference", required=True, index=True, copy=False, readonly=True,
        help="Opaque handle for this signature. It is not a name and cannot be "
             "traced to one — it exists so a person can be discussed in a log "
             "without inventing an identity for them.")
    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)

    embedding = fields.Text(
        string="Encrypted Signature", copy=False, groups="analitix.group_manager",
        help="The face vector, encrypted at rest. A list of numbers from which "
             "no image can be reconstructed.")
    embedding_dim = fields.Integer(string="Dimensions", readonly=True)
    model_name = fields.Char(string="Model", default="buffalo_l", required=True)

    first_seen = fields.Datetime(
        string="First Seen", required=True, index=True,
        default=lambda self: fields.Datetime.now())
    last_seen = fields.Datetime(
        string="Last Seen", required=True, index=True,
        default=lambda self: fields.Datetime.now())
    expires_at = fields.Datetime(
        string="Expires", required=True, index=True,
        help="When this signature is deleted. Set from the store's retention "
             "window on every sighting, so an active visitor's handle lives as "
             "long as their visit and not a minute longer.")
    match_count = fields.Integer(
        string="Sightings", default=1, readonly=True,
        help="How many crossings resolved to this signature during its life.")

    visitor_ids = fields.One2many(
        "analitix.visitor", "signature_id", string="Visits")
    visit_count = fields.Integer(compute="_compute_visit_count")
    door_ids = fields.Many2many(
        "analitix.door", relation="analitix_signature_door_rel",
        column1="signature_id", column2="door_id", string="Doors Used",
        help="Which entrances this person has used. With one door it is always "
             "the same door; with several it is the raw material for the "
             "cross-door re-identification the multi-entrance stores buy this for.")

    liveness_score = fields.Float(
        string="Liveness", digits=(3, 3),
        help="Confidence from the edge that this was a live face rather than a "
             "photograph held up to the camera. Recorded here so the phases "
             "that make consequential decisions can require a floor.")

    # --- phase 3: the optional bridge to a named customer ---
    partner_id = fields.Many2one(
        "res.partner", string="Customer", index=True, ondelete="set null",
        help="Set only when the customer handed over their details at the till "
             "and the store has customer identification switched on. Most "
             "signatures never get one and are deleted anonymous.")
    identified = fields.Boolean(
        string="Identified", index=True,
        help="This signature belongs to a customer the shop can name. It "
             "outlives the anonymous retention window — that is the point of "
             "it — but not forever: the store sets how long, and the same "
             "expiry job enforces it.")
    identified_on = fields.Datetime(string="Identified On", readonly=True)

    _reference_uniq = models.Constraint(
        "unique(reference)", "This signature reference already exists.")

    _store_expiry_idx = models.Index("(store_id, expires_at)")

    @api.depends("visitor_ids")
    def _compute_visit_count(self):
        for signature in self:
            signature.visit_count = len(signature.visitor_ids)

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    @api.model
    def _candidates(self, store, model_name):
        """Live signatures of one store, decrypted and unit-normalised.

        Not cached, unlike the staff set: this table churns constantly — a new
        signature every time a stranger walks in — so a cache would be stale
        within seconds and invalidating it on every write would cost more than
        it saves. It is bounded instead by the retention window, which is what
        keeps the scan small: a store only ever compares against the people who
        were there recently, never against its whole history.
        """
        crypto = self.env["analitix.crypto"]
        now = fields.Datetime.now()
        rows = self.sudo().search([
            ("store_id", "=", store.id),
            ("model_name", "=", model_name),
            ("expires_at", ">", now),
        ])
        out = []
        for row in rows:
            vector = crypto.decrypt_vector(row.embedding)
            if vector:
                out.append((row, crypto.normalize(vector)))
        return out

    @api.model
    def resolve(self, store, vector, door=None, model_name="buffalo_l",
                liveness=None):
        """Return ``(signature, is_new)`` for ``vector`` inside ``store``.

        Either finds the person among those seen recently, or mints a new
        anonymous handle for them.
        """
        crypto = self.env["analitix.crypto"]
        probe = crypto.normalize(vector)
        best_row, best_score = None, 0.0
        for row, known in self._candidates(store, model_name):
            if len(known) != len(probe):
                continue
            score = sum(a * b for a, b in zip(probe, known))
            if score > best_score:
                best_row, best_score = row, score

        # Cross-door matching is only meaningful where there is more than one
        # door. Reading it from the configuration rather than assuming it is
        # the whole point of the product.
        now = fields.Datetime.now()
        expiry = now + timedelta(minutes=store.reid_ttl_minutes)

        if best_row is not None and best_score >= store.reid_threshold:
            if door and door not in best_row.door_ids:
                best_row.sudo().door_ids = [(4, door.id)]
            best_row.sudo().write({
                "last_seen": now,
                "expires_at": expiry,
                "match_count": best_row.match_count + 1,
            })
            return best_row, False

        signature = self.sudo().create({
            "reference": self._next_reference(store),
            "store_id": store.id,
            "embedding": crypto.encrypt_vector(probe),
            "embedding_dim": len(probe),
            "model_name": model_name,
            "first_seen": now,
            "last_seen": now,
            "expires_at": expiry,
            "door_ids": [(6, 0, door.ids)] if door else False,
            "liveness_score": liveness or 0.0,
        })
        return signature, True

    @api.model
    def _greet_if_known(self, store, signature, visitor):
        """Tell the salesperson a customer they know has walked in.

        The whole value of identification from the shop's side: being able to
        say "good morning Gustavo" instead of "can I help you". The nudge goes
        to the person, never to a screen the customer can see — phase 4 handles
        the screens, and it applies its own rule about greeting somebody by
        name in front of the company they arrived with.
        """
        if not store.greet_known_customers or not signature.identified:
            return False
        partner = signature.partner_id
        if not partner:
            return False
        entrance = self.env["analitix.zone"].sudo().search([
            ("store_id", "=", store.id), ("kind", "=", "entrance")], limit=1)
        summary = _last_purchase_summary(self.env, partner)
        self.env["analitix.alert"].raise_alert(
            store, "known_customer",
            _("%(name)s just came in", name=partner.name),
            body=_("%(name)s is a returning customer.%(last)s",
                   name=partner.display_name,
                   last=(_("\nLast purchase: %s", summary) if summary else "")),
            zone=entrance or False, visitor=visitor, partner=partner)
        return True

    @api.model
    def _next_reference(self, store):
        """A handle that reads like an id and carries no identity."""
        sequence = self.env["ir.sequence"].sudo().next_by_code(
            "analitix.face.signature")
        if not sequence:
            sequence = fields.Datetime.now().strftime("%Y%m%d%H%M%S%f")
        return "%s-%s" % (store.code or store.id, sequence)

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------
    @api.model
    def _cron_expire(self, batch=5000):
        """Delete signatures past their store's retention window.

        This cron is not housekeeping, it is the retention promise. An
        anonymous face vector that is never deleted stops being short-lived
        data and becomes a biometric database nobody agreed to.
        """
        now = fields.Datetime.now()
        total = 0
        while True:
            expired = self.sudo().search([("expires_at", "<=", now)], limit=batch)
            if not expired:
                break
            total += len(expired)
            expired.unlink()
        if total:
            _logger.info("Analitix: expired %d anonymous face signature(s).", total)
        return True

    # ------------------------------------------------------------------
    # Asynchronous resolution (task 982, point 3)
    # ------------------------------------------------------------------
    @api.model
    def _run_visitor_resolve(self, job):
        """Turn crossings into visits, off the ingest request.

        Runs asynchronously because matching a face against everyone seen in the
        last hour is real work, and the edge agent must not be held waiting for
        it — the crossing is already safely stored by the time this runs.
        """
        Event = self.env["analitix.event"].sudo()
        Visitor = self.env["analitix.visitor"].sudo()
        crypto = self.env["analitix.crypto"]
        Staff = self.env["analitix.staff.signature"]
        Group = self.env["analitix.visit.group"].sudo()
        events = Event.browse(job._payload().get("event_ids") or []).exists()
        for event in events:
            vector = crypto.decrypt_vector(event.pending_embedding)
            if not vector:
                event.write({"pending_embedding": False})
                continue
            store = event.store_id

            # Staff first. An employee must never become a visit, and doing the
            # check here as well as at ingest covers the crossings whose
            # embedding the endpoint deferred rather than matching inline.
            sig_id, employee_id, score = Staff.match(store, vector)
            if employee_id:
                Staff.browse(sig_id)._register_match()
                event.write({
                    "pending_embedding": False, "counted": False,
                    "staff_id": employee_id, "match_score": score,
                })
                continue

            # A reading the edge could not vouch for is not trusted with a
            # decision when the store has asked for liveness. The crossing
            # still counts — being unsure whether a face was live is no reason
            # to lose a visitor.
            if store.require_liveness and event.liveness_score < store.liveness_min_score:
                event.write({"pending_embedding": False})
                continue

            signature, is_new = self.resolve(
                store, vector, door=event.door_id,
                model_name=event.embedding_model or "buffalo_l",
                liveness=event.liveness_score)
            visitor = Visitor._register_crossing(event, signature, is_new)

            vals = {
                "pending_embedding": False,
                "signature_id": signature.id,
                "visitor_id": visitor.id if visitor else False,
            }
            if visitor and event.direction == "in":
                self._greet_if_known(store, signature, visitor)
            if visitor:
                if event.pending_demographic_id and not visitor.demographic_id:
                    visitor.demographic_id = event.pending_demographic_id.id
                    vals["pending_demographic_id"] = False
                if (store.group_detection_enabled and event.direction == "in"
                        and not visitor.visit_group_id):
                    Group.assign(visitor, event)
            event.write(vals)
        return True


register_handler("visitor_resolve", "analitix.face.signature",
                 "_run_visitor_resolve")


def _last_purchase_summary(env, partner):
    """One short line about what this customer last bought.

    Short on purpose: it is read on a phone, by someone walking across a shop
    floor towards the person it describes.
    """
    order = env["pos.order"].sudo().search(
        [("partner_id", "=", partner.id),
         ("state", "in", ("paid", "done", "invoiced"))],
        order="date_order desc", limit=1)
    if not order:
        return ""
    line = order.lines[:1]
    product = line.product_id.display_name if line else ""
    return "%s · %s" % (
        fields.Date.to_string(order.date_order.date()), product or order.name)
