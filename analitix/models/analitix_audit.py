# -*- coding: utf-8 -*-
"""Append-only audit trail (task 984, point 6).

Odoo's chatter already answers *who changed this record*.  What it does not
answer, and what matters for a system holding biometric-derived data, is **who
looked**.  Reading a watch list, exporting a report that carries customers'
names next to their face signature, pausing a store's capture, rotating a
device key — none of those modify a business record, so none of them leave a
trace anywhere else.

The model is deliberately append-only for everyone, including administrators:
an audit trail that its own subject can edit is not evidence.  Enforced in code
here and in ``ir.model.access.csv`` (no write, no unlink for anybody).
"""
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AnalitixAuditLog(models.Model):
    _name = "analitix.audit.log"
    _description = "Analitix Audit Log"
    _order = "create_date desc, id desc"
    _rec_name = "action"

    action = fields.Selection(
        selection=[
            ("read_sensitive", "Read sensitive data"),
            ("export", "Exported a report"),
            ("key_rotate", "Rotated a device key"),
            ("key_revoke", "Revoked a device key"),
            ("kill_switch", "Used the capture kill switch"),
            ("anomaly", "Ingest anomaly detected"),
            ("auth_failure", "Rejected API credential"),
            ("elevated", "Elevated-control decision"),
            ("watchlist_add", "Watch-list entry created"),
            ("watchlist_confirm", "Watch-list entry confirmed"),
        ],
        required=True, index=True, readonly=True)
    user_id = fields.Many2one(
        "res.users", string="User", index=True, readonly=True,
        default=lambda self: self.env.user)
    store_id = fields.Many2one(
        "analitix.store", string="Store", index=True, readonly=True,
        ondelete="set null")
    company_id = fields.Many2one(
        "res.company", string="Company", index=True, readonly=True,
        default=lambda self: self.env.company)
    model_name = fields.Char(string="Model", readonly=True, index=True)
    res_id = fields.Integer(string="Record ID", readonly=True)
    record_count = fields.Integer(
        string="Records", readonly=True,
        help="How many records the action touched. A single read of one entry "
             "and a bulk export of the whole list are very different events.")
    note = fields.Char(string="Detail", readonly=True)
    ip_address = fields.Char(string="IP", readonly=True)

    _action_date_idx = models.Index("(action, create_date DESC)")

    # ------------------------------------------------------------------
    # Append-only
    # ------------------------------------------------------------------
    def write(self, vals):
        raise UserError(_(
            "Audit entries cannot be modified. A trail that can be edited by "
            "the people it records is not a trail."))

    def unlink(self):
        raise UserError(_(
            "Audit entries cannot be deleted. Use the retention cron if the "
            "trail has to be pruned on a documented schedule."))

    # ------------------------------------------------------------------
    # Writing entries
    # ------------------------------------------------------------------
    @api.model
    def log(self, action, model=None, res_id=None, store=None, note=None,
            count=1):
        """Record one auditable act. Never raises: a failure to log must not
        break the operation being logged, but it must be visible in the server
        log so a silently broken trail is not mistaken for a quiet one."""
        try:
            ip = False
            try:
                from odoo.http import request
                if request:
                    ip = request.httprequest.remote_addr
            except (RuntimeError, ImportError):
                ip = False
            return self.sudo().create({
                "action": action,
                "model_name": model,
                "res_id": res_id or 0,
                "store_id": store.id if store else False,
                "company_id": (store.company_id.id if store
                               else self.env.company.id),
                "note": note and note[:255] or False,
                "record_count": count,
                "ip_address": ip,
            })
        except Exception:  # noqa: BLE001
            _logger.exception("Analitix: could not write an audit entry (%s).",
                              action)
            return self.browse()


class AnalitixAuditedMixin(models.AbstractModel):
    """Mixin for models whose *reads* must be audited.

    Inheriting models get their ``search_read`` and ``read`` logged. It is
    intentionally coarse — one entry per call with a record count, not one per
    field — because the question being answered is "did someone go through the
    watch list?", and a per-field trail would bury that in noise.

    Phase 5 mixes this into the watch list; phase 3 mixes it into the
    identified-customer signatures.
    """
    _name = "analitix.audited.mixin"
    _description = "Analitix — Read-Audited Model"

    #: subclasses may narrow this
    _audit_action = "read_sensitive"

    def _audit_read(self, count=None):
        # Internal machinery reads these models constantly (name_get during a
        # form render, the ORM resolving a many2one). Logging those would drown
        # the deliberate human reads this exists to surface, so system context
        # is skipped.
        if self.env.su or self.env.context.get("analitix_skip_audit"):
            return
        self.env["analitix.audit.log"].sudo().log(
            action=self._audit_action,
            model=self._name,
            res_id=self.ids[0] if len(self.ids) == 1 else 0,
            store=self[:1].store_id if "store_id" in self._fields else None,
            count=count if count is not None else len(self),
            note=_("Consulted %s record(s)", count if count is not None else len(self)),
        )

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None,
                    order=None, **kwargs):
        res = super().search_read(
            domain=domain, fields=fields, offset=offset, limit=limit,
            order=order, **kwargs)
        self._audit_read(count=len(res))
        return res

    def read(self, fields=None, load="_classic_read"):
        res = super().read(fields=fields, load=load)
        self._audit_read(count=len(res))
        return res
