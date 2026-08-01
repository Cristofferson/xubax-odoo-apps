# -*- coding: utf-8 -*-
"""Employee face signatures, used only to *remove* them from the counts.

Why this matters more than it sounds: in a jewellery store with four staff, the
team crosses the door dozens of times a day — deliveries, lunch, the bank.  Left
in, they can be a third of the "visitors", and the conversion rate the owner is
paying to see comes out badly wrong and consistently pessimistic.

Two places can do the matching, and both are supported on purpose:

* **On the edge** (preferred).  The agent pulls its store's signatures from
  ``/analitix/api/v1/staff_signatures`` and decides locally, so the crossing
  arrives already labelled and no embedding ever crosses the network.
* **On the server**, asynchronously.  The edge posts the embedding, the ingest
  controller answers immediately, and a queued job resolves the match. Slower,
  but it works with a thin agent on hardware that cannot hold the signature set.

Either way the embedding is stored encrypted (task 984) and no image exists at
any point in the chain.
"""
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

from .analitix_crypto import decode_embedding
from .analitix_job import register_handler


class AnalitixStaffSignature(models.Model):
    _name = "analitix.staff.signature"
    _description = "Analitix Staff Face Signature"
    _inherit = ["mail.thread"]
    _order = "store_id, employee_id"

    employee_id = fields.Many2one(
        "hr.employee", string="Employee", required=True, index=True,
        ondelete="cascade", tracking=True)
    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade", tracking=True,
        help="Signatures are scoped to a store: an employee of store A is not "
             "silently excluded from store B's counts. Enrol them in both if "
             "they genuinely work in both.")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)
    active = fields.Boolean(default=True, tracking=True)

    embedding = fields.Text(
        string="Encrypted Signature", copy=False, groups="analitix.group_manager",
        help="The employee's face embedding, encrypted at rest. It is a vector "
             "of numbers from which no image can be reconstructed.")
    embedding_dim = fields.Integer(string="Dimensions", readonly=True)
    model_name = fields.Char(
        string="Model", default="buffalo_l", required=True,
        help="Which face model produced this vector. Embeddings from different "
             "models are not comparable, so matching only ever compares "
             "signatures sharing this value.")
    enrolled_on = fields.Datetime(
        string="Enrolled", default=lambda self: fields.Datetime.now(),
        readonly=True)
    enrolled_by_id = fields.Many2one(
        "res.users", string="Enrolled By", readonly=True,
        default=lambda self: self.env.user)
    last_match = fields.Datetime(string="Last Match", readonly=True, copy=False)
    match_count = fields.Integer(string="Matches", readonly=True, copy=False)
    note = fields.Text(string="Notes")

    @api.constrains("embedding", "model_name")
    def _check_embedding(self):
        for sig in self:
            if sig.embedding and not sig.embedding_dim:
                raise ValidationError(_(
                    "This signature carries no usable vector. Re-enrol the "
                    "employee from the edge enrolment tool."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._invalidate_signature_cache()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {"embedding", "active", "store_id", "model_name"} & set(vals):
            self._invalidate_signature_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self._invalidate_signature_cache()
        return res

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    def _invalidate_signature_cache(self):
        """Drop the decrypted-signature cache across *every* Odoo worker.

        This has to be the registry-level clear, not a dict on the process:
        Odoo runs several worker processes, and a signature deleted by the
        worker serving the browser would otherwise stay live in the worker
        serving the ingest endpoint — quietly excluding an employee who was
        removed hours ago. ``clear_cache`` signals the whole cluster.
        """
        self.env.registry.clear_cache()

    @api.model
    @tools.ormcache("store_id")
    def _store_signatures(self, store_id):
        """Decrypted, unit-normalised signatures of one store.

        Cached because decryption plus normalisation is real work and the
        ingest path would otherwise redo it on every crossing. Returned as
        tuples so the cached value cannot be mutated by a caller.
        """
        crypto = self.env["analitix.crypto"]
        entries = []
        for sig in self.sudo().search([
                ("store_id", "=", store_id), ("active", "=", True)]):
            vector = crypto.decrypt_vector(sig.embedding)
            if vector:
                entries.append((sig.id, sig.employee_id.id,
                                tuple(crypto.normalize(vector)), sig.model_name))
        return tuple(entries)

    @api.model
    def match(self, store, vector, model_name="buffalo_l"):
        """Best staff match for ``vector``, or ``(None, None, 0.0)``.

        Returns the signature, the employee and the score so the caller can
        record *how* confident the exclusion was; a store that later sees its
        counts look wrong can then re-tune its threshold against real scores
        rather than by trial and error.
        """
        if not vector or not store.exclude_staff:
            return None, None, 0.0
        crypto = self.env["analitix.crypto"]
        probe = crypto.normalize(vector)
        best_sig = best_emp = None
        best_score = 0.0
        for sig_id, emp_id, known, known_model in self._store_signatures(store.id):
            if known_model != model_name or len(known) != len(probe):
                continue
            # Both sides are unit vectors, so the dot product *is* the cosine.
            score = sum(a * b for a, b in zip(probe, known))
            if score > best_score:
                best_sig, best_emp, best_score = sig_id, emp_id, score
        if best_score >= store.staff_match_threshold:
            return best_sig, best_emp, best_score
        return None, None, best_score

    @api.model
    def enrol(self, store, employee, payload, model_name="buffalo_l"):
        """Create or refresh a signature from an inbound embedding payload."""
        vector = decode_embedding(payload)
        if not vector:
            raise ValidationError(_("The enrolment payload carried no vector."))
        crypto = self.env["analitix.crypto"]
        normalised = crypto.normalize(vector)
        existing = self.search([
            ("store_id", "=", store.id),
            ("employee_id", "=", employee.id),
            ("model_name", "=", model_name),
        ], limit=1)
        vals = {
            "embedding": crypto.encrypt_vector(normalised),
            "embedding_dim": len(normalised),
            "model_name": model_name,
            "active": True,
        }
        if existing:
            existing.write(vals)
            return existing
        vals.update({"store_id": store.id, "employee_id": employee.id})
        return self.create(vals)

    def _register_match(self):
        """Bump the usage counters, cheaply and without tripping tracking."""
        for sig in self:
            sig.sudo().write({
                "last_match": fields.Datetime.now(),
                "match_count": sig.match_count + 1,
            })

    # ------------------------------------------------------------------
    # Asynchronous matching (task 982, point 3)
    # ------------------------------------------------------------------
    @api.model
    def _run_staff_match(self, job):
        """Resolve embeddings the ingest endpoint deferred.

        Runs off the request path so a store with hundreds of enrolled staff
        never slows the agent down. Whatever the outcome, the embedding is
        wiped afterwards: the event table is a traffic log, and leaving face
        vectors sitting in it would quietly turn it into a biometric database.
        """
        Event = self.env["analitix.event"].sudo()
        crypto = self.env["analitix.crypto"]
        events = Event.browse(job._payload().get("event_ids") or []).exists()
        for event in events:
            vector = crypto.decrypt_vector(event.pending_embedding)
            if not vector:
                event.write({"pending_embedding": False})
                continue
            sig_id, employee_id, score = self.match(event.store_id, vector)
            vals = {"match_score": score, "pending_embedding": False}
            if employee_id:
                vals.update({"counted": False, "staff_id": employee_id})
                self.browse(sig_id)._register_match()
            event.write(vals)
        return True


register_handler("staff_match", "analitix.staff.signature", "_run_staff_match")
