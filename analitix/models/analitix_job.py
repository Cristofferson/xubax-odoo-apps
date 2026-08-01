# -*- coding: utf-8 -*-
"""A small, self-contained job queue.

Why not just do the work inline: the edge agent is holding an HTTP connection
open while Odoo answers.  Face matching, signage triggers and CRM writes all
take time that has nothing to do with *storing a crossing*, and an integration
that hangs — a slow Xibo CMS, an unreachable WhatsApp gateway — would then stall
the store's counting.  The rule from task 982 is explicit: **an outbound
integration failing must never stop data capture.**  So the controller records
the fact and returns; everything else happens here.

Why not ``queue_job``: it is a fine module, but it is an OCA dependency the
customer would have to install, and this addon is sold on apps.odoo.com to
stores that will not want a second moving part.  If ``queue_job`` *is* present
on an instance, nothing here conflicts with it.

Handlers are registered by other phases via ``_JOB_HANDLERS``, so adding a new
kind of asynchronous work later does not mean touching this file.
"""
import json
import logging
import traceback
from datetime import timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

#: ``kind`` -> name of the model method to call as ``model._run_<handler>(job)``
JOB_HANDLERS = {}


def register_handler(kind, model_name, method_name):
    """Declare which model method runs a given job kind."""
    JOB_HANDLERS[kind] = (model_name, method_name)


class AnalitixJob(models.Model):
    _name = "analitix.job"
    _description = "Analitix Background Job"
    _order = "priority, scheduled_at, id"

    kind = fields.Char(required=True, index=True, readonly=True)
    payload = fields.Text(
        readonly=True,
        help="JSON arguments for the handler. Kept as text so a job survives a "
             "module upgrade that changes the models it refers to.")
    store_id = fields.Many2one(
        "analitix.store", string="Store", index=True, ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, readonly=True)
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="pending", required=True, index=True, readonly=True)
    priority = fields.Integer(
        default=10,
        help="Lower runs first. Time-sensitive work — a welcome message that "
             "is worthless if it arrives after the customer has walked past the "
             "screen — belongs below 10.")
    scheduled_at = fields.Datetime(
        default=lambda self: fields.Datetime.now(), required=True, index=True,
        help="Not before this moment. Retries push it into the future.")
    started_at = fields.Datetime(readonly=True)
    finished_at = fields.Datetime(readonly=True)
    attempts = fields.Integer(default=0, readonly=True)
    max_attempts = fields.Integer(default=5)
    error = fields.Text(readonly=True)
    duration_ms = fields.Integer(string="Duration (ms)", readonly=True)

    # Partial index: the cron only ever looks for pending work, and indexing
    # the done rows would grow without bound for no benefit.
    _pending_idx = models.Index(
        "(state, priority, scheduled_at) WHERE state = 'pending'")

    # ------------------------------------------------------------------
    # Enqueueing
    # ------------------------------------------------------------------
    @api.model
    def enqueue(self, kind, payload=None, store=None, priority=10, delay_s=0):
        """Queue one unit of work and return the job."""
        scheduled = fields.Datetime.now()
        if delay_s:
            scheduled += timedelta(seconds=delay_s)
        return self.sudo().create({
            "kind": kind,
            "payload": json.dumps(payload or {}),
            "store_id": store.id if store else False,
            "priority": priority,
            "scheduled_at": scheduled,
        })

    def _payload(self):
        self.ensure_one()
        try:
            return json.loads(self.payload or "{}")
        except ValueError:
            return {}

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------
    @api.model
    def _cron_run(self, limit=200):
        """Drain the queue.

        Jobs are claimed with ``FOR UPDATE SKIP LOCKED`` rather than by
        committing a 'running' flag: two workers can then drain the queue
        side by side and simply never see the same row, with no window in
        which a crash leaves a job stuck in ``running`` forever.
        """
        self.env.cr.execute("""
            SELECT id FROM analitix_job
            WHERE state = 'pending' AND scheduled_at <= now() AT TIME ZONE 'UTC'
            ORDER BY priority, scheduled_at, id
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        """, (limit,))
        job_ids = [row[0] for row in self.env.cr.fetchall()]
        for job in self.sudo().browse(job_ids):
            job._run_one()
        return True

    def _run_one(self):
        """Run one job, isolated by a savepoint.

        The savepoint is what keeps a poisoned payload from taking the whole
        batch with it: when the handler raises, only its own work is undone and
        the transaction stays usable, so the failure can actually be *recorded*
        rather than rolled back along with everything else.

        Savepoints rather than commits on purpose — an explicit commit would
        also make this unrunnable inside a test, and code that cannot be tested
        the way it runs in production is code nobody can trust.
        """
        self.ensure_one()
        started = fields.Datetime.now()
        self.sudo().write({
            "state": "running", "started_at": started,
            "attempts": self.attempts + 1,
        })
        handler = JOB_HANDLERS.get(self.kind)
        if not handler:
            self.sudo().write({
                "state": "failed",
                "error": _("No handler is registered for job kind '%s'.", self.kind),
                "finished_at": fields.Datetime.now(),
            })
            return False

        model_name, method_name = handler
        try:
            with self.env.cr.savepoint():
                method = getattr(self.env[model_name].sudo(), method_name)
                method(self)
        except Exception:  # noqa: BLE001 — a job must never take the cron down
            error = traceback.format_exc()
            _logger.warning("Analitix job %s (%s) failed:\n%s",
                            self.id, self.kind, error)
            vals = {"error": error, "finished_at": fields.Datetime.now()}
            if self.attempts >= self.max_attempts:
                vals["state"] = "failed"
            else:
                # Exponential backoff: a gateway that is down stays down for a
                # while, and hammering it every minute helps nobody.
                vals["state"] = "pending"
                vals["scheduled_at"] = fields.Datetime.now() + timedelta(
                    seconds=min(60 * (2 ** self.attempts), 3600))
            self.sudo().write(vals)
            return False

        finished = fields.Datetime.now()
        self.sudo().write({
            "state": "done",
            "finished_at": finished,
            "duration_ms": int((finished - started).total_seconds() * 1000),
            "error": False,
        })
        return True

    def action_retry(self):
        """Put a failed job back in line, from the UI."""
        self.sudo().write({
            "state": "pending", "error": False, "attempts": 0,
            "scheduled_at": fields.Datetime.now(),
        })
        return True

    @api.model
    def _cron_vacuum(self, days=7):
        """Drop old successful jobs. Failures are kept — they are evidence."""
        cutoff = fields.Datetime.now() - timedelta(days=days)
        self.sudo().search([
            ("state", "=", "done"), ("finished_at", "<", cutoff),
        ]).unlink()
        return True

    # ------------------------------------------------------------------
    # Observability helpers (task 982, point 4)
    # ------------------------------------------------------------------
    @api.model
    def queue_stats(self):
        """Backlog summary for the technical dashboard."""
        late_cutoff = fields.Datetime.now() - timedelta(minutes=15)
        pending = self.sudo().search_count([("state", "=", "pending")])
        late = self.sudo().search_count([
            ("state", "=", "pending"), ("scheduled_at", "<", late_cutoff)])
        failed = self.sudo().search_count([("state", "=", "failed")])
        return {"pending": pending, "late": late, "failed": failed}
