# -*- coding: utf-8 -*-
"""The watch list — the most consequential thing in this addon.

Everything else here measures behaviour. This names people, and a false
positive lands on a real person who did nothing. So it is built with more
friction than any other feature, and the friction is the feature:

**Nobody is added automatically.** Ever. There is no code path that creates an
entry. A person puts a name on this list, in writing, with a reason.

**Two people, not one** (task 984, point 9). An entry is created in *draft* and
does nothing at all until a second authorised user confirms it. One angry
afternoon should not be enough to mark somebody.

**It expires.** Every entry carries a review date and an expiry. A list that
only grows becomes a list nobody trusts and nobody prunes, and somebody who had
a bad day three years ago is still on it.

**A match is a prompt to pay attention, never an accusation and never an
action.** No door locks, no automatic report, no message on any screen. A
person is told, quietly, and a person decides.

**Reads are audited, not just writes** (task 984, point 6). Going through this
list is itself an act worth recording — Odoo's chatter would only ever show who
changed something, never who looked.

**One role, outside the commercial hierarchy** (task 983). A store manager who
can see conversion figures does not get this by default; a compliance role
does. Someone's presence on a watch list is not sales data.

Match confidence is deliberately stricter than anywhere else in the product,
and liveness is required: a photograph held to a camera must not be able to put
a real person under suspicion.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .analitix_crypto import decode_embedding

_logger = logging.getLogger(__name__)


class AnalitixWatchPerson(models.Model):
    _name = "analitix.watch.person"
    _description = "Analitix Watch-list Entry"
    # Reads are logged, not only writes. See the module docstring.
    # mail.activity.mixin is not decoration: the review cycle is delivered as a
    # real activity on a real person's dashboard, and without it the periodic
    # review is a date in a column that nobody is ever shown.
    _inherit = ["mail.thread", "mail.activity.mixin", "analitix.audited.mixin"]
    _audit_action = "read_sensitive"
    _order = "state, expires_on, id desc"
    _rec_name = "reference"

    reference = fields.Char(
        string="Reference", required=True, copy=False, readonly=True,
        index=True, default=lambda self: _("New"),
        help="An opaque handle. Deliberately not a name: staff acting on an "
             "alert need to know somebody is worth a second look, not to "
             "circulate an identity.")
    display_label = fields.Char(
        string="Label", required=True, tracking=True,
        help="How this entry is described internally — 'the man from the "
             "March 4th incident'. Keep it factual: this is read by people who "
             "were not there.")
    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade", tracking=True,
        help="Matching happens within this store only. Sharing a watch list "
             "across a chain is a decision with far wider consequences and "
             "belongs to the corporate phase, behind its own control.")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)

    # --- the biometric part ---
    embedding = fields.Text(
        string="Encrypted Signature", copy=False,
        groups="analitix.group_security",
        help="Face vector, encrypted at rest. No photograph is stored here or "
             "anywhere else in Analitix.")
    embedding_dim = fields.Integer(string="Dimensions", readonly=True)
    model_name = fields.Char(string="Model", default="buffalo_l", required=True)

    # --- why ---
    reason = fields.Text(
        string="Reason", required=True, tracking=True,
        help="What happened, factually and dated. This is the record somebody "
             "will read in a year when deciding whether the entry still "
             "belongs here.")
    incident_date = fields.Date(
        string="Incident Date", required=True, tracking=True,
        default=fields.Date.context_today)
    severity = fields.Selection(
        selection=[
            ("watch", "Worth a second look"),
            ("incident", "Confirmed incident"),
            ("repeat", "Repeated incidents"),
        ],
        string="Severity", default="watch", required=True, tracking=True)

    # --- double control (task 984, point 9) ---
    state = fields.Selection(
        selection=[
            ("draft", "Awaiting confirmation"),
            ("active", "Active"),
            ("expired", "Expired"),
            ("revoked", "Removed"),
        ],
        string="Status", default="draft", required=True, index=True,
        tracking=True,
        help="A draft entry matches nothing at all. It becomes active only "
             "when a second authorised person confirms it.")
    created_by_id = fields.Many2one(
        "res.users", string="Added By", readonly=True, tracking=True,
        default=lambda self: self.env.user)
    confirmed_by_id = fields.Many2one(
        "res.users", string="Confirmed By", readonly=True, tracking=True)
    confirmed_on = fields.Datetime(string="Confirmed On", readonly=True)
    revoked_by_id = fields.Many2one(
        "res.users", string="Removed By", readonly=True, tracking=True)
    revoke_reason = fields.Char(string="Removal Reason", tracking=True)

    # --- expiry and review ---
    review_on = fields.Date(
        string="Review On", required=True, tracking=True,
        help="When somebody should look at this again and decide whether it "
             "still belongs on the list.")
    expires_on = fields.Date(
        string="Expires On", required=True, tracking=True,
        help="After this the entry stops matching, automatically. A list that "
             "only grows is a list nobody trusts.")

    match_ids = fields.One2many(
        "analitix.watch.match", "person_id", string="Matches")
    match_count = fields.Integer(compute="_compute_match_count")
    last_match = fields.Datetime(string="Last Match", readonly=True)

    _reference_uniq = models.Constraint(
        "unique(reference)", "That watch-list reference already exists.")
    _dates_ordered = models.Constraint(
        "CHECK(expires_on >= review_on)",
        "An entry cannot expire before the date it is due for review.")
    _store_state_idx = models.Index("(store_id, state, expires_on)")

    # ------------------------------------------------------------------
    @api.depends("match_ids")
    def _compute_match_count(self):
        for person in self:
            person.match_count = len(person.match_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", _("New")) == _("New"):
                vals["reference"] = self.env["ir.sequence"].next_by_code(
                    "analitix.watch.person") or _("New")
            store = self.env["analitix.store"].browse(vals.get("store_id"))
            today = fields.Date.context_today(self)
            if not vals.get("review_on"):
                vals["review_on"] = fields.Date.add(
                    today, days=store.watchlist_review_days or 90)
            if not vals.get("expires_on"):
                vals["expires_on"] = fields.Date.add(
                    today, days=store.watchlist_expiry_days or 365)
        entries = super().create(vals_list)
        for entry in entries:
            self.env["analitix.audit.log"].sudo().log(
                action="watchlist_add", model=self._name, res_id=entry.id,
                store=entry.store_id,
                note=_("Watch-list entry %s created (awaiting confirmation)",
                       entry.reference))
        return entries

    @api.constrains("expires_on")
    def _check_expiry_bounded(self):
        """Nobody stays on this list indefinitely by accident."""
        for entry in self:
            limit = fields.Date.add(
                fields.Date.context_today(entry),
                days=entry.store_id.watchlist_max_days or 730)
            if entry.expires_on > limit:
                raise ValidationError(_(
                    "This entry would stay active beyond the store's maximum "
                    "of %(days)s days. Somebody has to look at it again before "
                    "then.", days=entry.store_id.watchlist_max_days or 730))

    # ------------------------------------------------------------------
    # Double control
    # ------------------------------------------------------------------
    def action_confirm(self):
        """A second authorised person makes the entry live.

        The person who added it cannot be the one who confirms it. That is the
        entire point: one angry afternoon should not be enough to mark
        somebody, and a rule that a determined individual can satisfy alone is
        not a control.
        """
        for entry in self:
            if entry.state != "draft":
                raise UserError(_("Only a draft entry can be confirmed."))
            if entry.created_by_id == self.env.user:
                raise UserError(_(
                    "The person who added an entry cannot confirm it. A second "
                    "authorised person has to agree — that is what makes this "
                    "a control rather than a formality."))
            if not entry.embedding:
                raise UserError(_(
                    "This entry has no face signature, so it could never match "
                    "anything. Enrol it from the edge tool first."))
            entry.write({
                "state": "active",
                "confirmed_by_id": self.env.user.id,
                "confirmed_on": fields.Datetime.now(),
            })
            entry.message_post(body=_(
                "Confirmed by %(user)s. This entry is now active until "
                "%(date)s.", user=self.env.user.display_name,
                date=entry.expires_on))
            self.env["analitix.audit.log"].sudo().log(
                action="watchlist_confirm", model=self._name, res_id=entry.id,
                store=entry.store_id,
                note=_("Entry %(ref)s confirmed by %(user)s",
                       ref=entry.reference, user=self.env.user.display_name))
        return True

    def action_revoke(self):
        for entry in self:
            entry.write({
                "state": "revoked",
                "revoked_by_id": self.env.user.id,
            })
            entry.message_post(body=_(
                "Removed from the watch list by %s.",
                self.env.user.display_name))
            self.env["analitix.audit.log"].sudo().log(
                action="elevated", model=self._name, res_id=entry.id,
                store=entry.store_id,
                note=_("Entry %s removed from the watch list", entry.reference))
        return True

    def action_extend(self):
        """Push the review and expiry out — but only by another full cycle,
        and it is recorded. Extending is a decision, not a default."""
        for entry in self:
            store = entry.store_id
            entry.write({
                "review_on": fields.Date.add(
                    fields.Date.context_today(entry),
                    days=store.watchlist_review_days or 90),
                "expires_on": fields.Date.add(
                    fields.Date.context_today(entry),
                    days=store.watchlist_expiry_days or 365),
                "state": "active" if entry.state == "expired" else entry.state,
            })
            entry.message_post(body=_(
                "Reviewed and extended by %(user)s to %(date)s.",
                user=self.env.user.display_name, date=entry.expires_on))
        return True

    # ------------------------------------------------------------------
    # Enrolment
    # ------------------------------------------------------------------
    @api.model
    def enrol(self, entry, payload, model_name="buffalo_l"):
        """Attach a face vector to a draft entry."""
        vector = decode_embedding(payload)
        if not vector:
            raise ValidationError(_("The enrolment payload carried no vector."))
        crypto = self.env["analitix.crypto"]
        normalised = crypto.normalize(vector)
        entry.write({
            "embedding": crypto.encrypt_vector(normalised),
            "embedding_dim": len(normalised),
            "model_name": model_name,
        })
        return entry

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    @api.model
    def check(self, store, vector, visitor=None, liveness=0.0,
              model_name="buffalo_l"):
        """Compare an arriving face against this store's active entries.

        Returns the matched entry or an empty recordset. Deliberately strict,
        and it refuses to decide at all on a reading the edge could not vouch
        for: a photograph held up to a camera must never be able to put a real
        person under suspicion.
        """
        if not store.watchlist_enabled or not vector:
            return self.browse()
        if liveness < store.watchlist_min_liveness:
            _logger.info(
                "Analitix: skipping a watch-list check on a low-liveness "
                "reading at store %s.", store.display_name)
            return self.browse()

        crypto = self.env["analitix.crypto"]
        probe = crypto.normalize(vector)
        today = fields.Date.context_today(self)
        candidates = self.sudo().search([
            ("store_id", "=", store.id),
            ("state", "=", "active"),
            ("expires_on", ">=", today),
            ("model_name", "=", model_name),
        ])
        best, best_score = self.browse(), 0.0
        for entry in candidates:
            known = crypto.decrypt_vector(entry.embedding)
            if not known or len(known) != len(probe):
                continue
            score = sum(a * b for a, b in zip(probe, crypto.normalize(known)))
            if score > best_score:
                best, best_score = entry, score

        if not best or best_score < store.watchlist_threshold:
            return self.browse()

        best._raise_match(visitor, best_score, liveness)
        return best

    def _raise_match(self, visitor, score, liveness):
        """Tell the restricted group, quietly. Nothing else happens."""
        self.ensure_one()
        store = self.store_id
        recipients = store.watchlist_user_ids
        if not recipients:
            _logger.warning(
                "Analitix: store %s has a watch list but nobody to notify.",
                store.display_name)

        match = self.env["analitix.watch.match"].sudo().create({
            "person_id": self.id,
            "store_id": store.id,
            "visitor_id": visitor.id if visitor else False,
            "score": score,
            "liveness": liveness,
        })
        # Never the zone salesperson, and never a screen: this goes to a
        # deliberately narrow, configured group.
        for user in recipients:
            alert = self.env["analitix.alert"].raise_alert(
                store, "watchlist",
                _("Worth a look near the entrance"),
                body=_(
                    "A person matching watch-list entry %(ref)s (%(label)s) "
                    "has come in.\n\n%(reason)s\n\nThis is a prompt to pay "
                    "attention, not an accusation and not an instruction. "
                    "Confidence %(score).0f%%. Somebody should look, and "
                    "somebody should decide.",
                    ref=self.reference, label=self.display_label,
                    reason=self.reason or "", score=score * 100),
                visitor=visitor, user=user)
            if alert and not match.alert_id:
                match.sudo().alert_id = alert.id

        self.sudo().write({"last_match": fields.Datetime.now()})
        self.env["analitix.audit.log"].sudo().log(
            action="elevated", model=self._name, res_id=self.id, store=store,
            note=_("Watch-list match on %(ref)s at %(score).2f",
                   ref=self.reference, score=score))
        return match

    # ------------------------------------------------------------------
    # Expiry and review
    # ------------------------------------------------------------------
    @api.model
    def _cron_expire(self):
        """Expire what is past its date and ask a human about what is due.

        Expiry is automatic; *removal* is not. The entry stops matching and
        stays visible, because the record of why somebody was on the list is
        part of the audit trail even after it stops being acted on.
        """
        today = fields.Date.context_today(self)
        expiring = self.sudo().search([
            ("state", "=", "active"), ("expires_on", "<", today)])
        for entry in expiring:
            entry.write({"state": "expired"})
            entry.message_post(body=_(
                "Expired automatically. It no longer matches anything; a "
                "person has to review and extend it for that to change."))

        due = self.sudo().search([
            ("state", "=", "active"), ("review_on", "<=", today)])
        for entry in due:
            responsible = entry.store_id.watchlist_user_ids[:1] or entry.created_by_id
            if not responsible:
                continue
            try:
                entry.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Review watch-list entry %s", entry.reference),
                    note=_(
                        "This entry is due for review. Does it still belong on "
                        "the list? Extending is a decision — the default is to "
                        "let it lapse."),
                    user_id=responsible.id)
                # Ask again in a month — but never past the entry's own
                # expiry. An entry with three weeks left to run would otherwise
                # be pushed to a review date beyond its expiry, which the date
                # constraint rejects, and one rejected write takes the whole
                # nightly batch down with it.
                entry.write({
                    "review_on": min(fields.Date.add(today, days=30),
                                     entry.expires_on)})
            except ValueError:
                _logger.warning(
                    "Analitix: could not raise a review activity for entry %s.",
                    entry.id)
        return True


class AnalitixWatchMatch(models.Model):
    """One sighting, and what a human made of it.

    The outcome field matters more than it looks: without it the list can never
    be evaluated, and a watch list nobody evaluates is one that quietly
    accumulates people who should not be on it.
    """
    _name = "analitix.watch.match"
    _description = "Analitix Watch-list Match"
    _inherit = ["analitix.audited.mixin"]
    _audit_action = "read_sensitive"
    _order = "matched_at desc, id desc"
    _rec_name = "person_id"

    person_id = fields.Many2one(
        "analitix.watch.person", string="Entry", required=True, index=True,
        ondelete="cascade")
    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, readonly=True)
    visitor_id = fields.Many2one(
        "analitix.visitor", string="Visit", ondelete="set null")
    alert_id = fields.Many2one(
        "analitix.alert", string="Alert", ondelete="set null")

    matched_at = fields.Datetime(
        string="Matched", required=True, index=True,
        default=lambda self: fields.Datetime.now())
    score = fields.Float(string="Confidence", digits=(3, 3))
    liveness = fields.Float(string="Liveness", digits=(3, 3))

    outcome = fields.Selection(
        selection=[
            ("pending", "Not reviewed"),
            ("wrong_person", "Wrong person"),
            ("uneventful", "Correct match, nothing happened"),
            ("incident", "Correct match, incident"),
        ],
        string="Outcome", default="pending", required=True, index=True,
        help="Filled in by whoever looked. 'Wrong person' is the most "
             "important value here: a list with false positives nobody records "
             "is a list nobody can fix.")
    note = fields.Text(string="Note")

    _store_matched_idx = models.Index("(store_id, matched_at DESC)")

    def action_wrong_person(self):
        """Mark a false positive, loudly.

        A false positive on this list is somebody who did nothing being watched
        because of a machine, so it is posted to the entry's own log where the
        next reviewer will see it.
        """
        for match in self:
            match.write({"outcome": "wrong_person"})
            match.person_id.message_post(body=_(
                "%(user)s reviewed a match on %(date)s and reported it as the "
                "WRONG PERSON. If this keeps happening, the entry's signature "
                "is poor and it should be removed rather than re-enrolled.",
                user=self.env.user.display_name,
                date=fields.Datetime.to_string(match.matched_at)))
        return True
