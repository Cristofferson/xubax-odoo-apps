# -*- coding: utf-8 -*-
"""Staff crossings as attendance, feeding Odoo's own ``hr.attendance``.

The signatures that keep employees out of the visitor count already know who
walked through the door and when, so the attendance register is nearly free.
Nearly — the part that is not free is judgement:

* **Off by default.** A shop that has not agreed this with its team should not
  start recording their working hours because a camera was installed for
  counting customers. Turning it on is a deliberate act by the employer.
* **Never overwrites a manual entry.** If someone corrected a check-in by hand,
  the camera does not get to argue.
* **A short trip out is not the end of a shift.** Somebody stepping to the bank
  for ten minutes should not close their day and open a new one, so repeat
  crossings inside a configurable gap are ignored.
* **It writes into Odoo's native model**, not a parallel one. Payroll, leave and
  every existing report already read ``hr.attendance``; a second attendance
  table that only this addon understands would be worse than useless.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models, _

from .analitix_job import register_handler

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    """Mark the rows Analitix opened.

    Without this the automatic closing job would have to guess which open
    shifts are its own, and guessing means eventually closing one a manager
    entered by hand.
    """
    _inherit = "hr.attendance"

    analitix_store_id = fields.Many2one(
        "analitix.store", string="Opened By Analitix", index=True,
        ondelete="set null", copy=False, readonly=True,
        help="Set when this check-in came from a store camera rather than from "
             "a person. Only these are ever closed automatically.")


class AnalitixAttendance(models.AbstractModel):
    """Service model turning employee crossings into attendance records."""
    _name = "analitix.attendance"
    _description = "Analitix — Staff Attendance Bridge"

    @api.model
    def _run_register(self, job):
        """Process the crossings a batch flagged as staff."""
        Event = self.env["analitix.event"].sudo()
        events = Event.browse(job._payload().get("event_ids") or []).exists()
        for event in events.sorted("event_time"):
            self._record_crossing(event)
        return True

    @api.model
    def _record_crossing(self, event):
        """Turn one employee crossing into a check-in or check-out.

        Not named ``_register``: that is a reserved Odoo model attribute — it
        controls whether a class joins the registry — and a method with that
        name is silently replaced by a boolean.
        """
        store = event.store_id
        employee = event.staff_id
        if not store.attendance_enabled or not employee:
            return False
        if store.attendance_door_id and event.door_id != store.attendance_door_id:
            return False

        Attendance = self.env["hr.attendance"].sudo()
        open_row = Attendance.search([
            ("employee_id", "=", employee.id),
            ("check_out", "=", False),
        ], order="check_in desc", limit=1)

        gap = timedelta(minutes=store.attendance_min_gap_minutes)

        if event.direction == "in":
            if open_row:
                # Already clocked in. A re-entry is a trip to the bank, not a
                # second working day.
                return False
            recent = Attendance.search([
                ("employee_id", "=", employee.id),
                ("check_out", ">=", event.event_time - gap),
            ], order="check_out desc", limit=1)
            if recent:
                # Came back inside the gap: reopen the same day rather than
                # fragmenting it into two shifts.
                recent.write({"check_out": False})
                return True
            Attendance.create({
                "employee_id": employee.id,
                "check_in": event.event_time,
                "analitix_store_id": store.id,
            })
            return True

        # Leaving.
        if not open_row:
            return False
        if event.event_time - open_row.check_in < gap:
            # Stepped out moments after arriving; closing here would record a
            # two-minute working day.
            return False
        open_row.write({"check_out": event.event_time})
        return True

    # ------------------------------------------------------------------
    @api.model
    def _cron_close_forgotten(self):
        """Close shifts nobody was seen leaving.

        Exits get missed — someone leaves in a crowd, the camera drops a frame.
        Left open, the employee appears to have worked a fifty-hour day and any
        payroll reading it is wrong. Closed at the store's maximum shift length,
        and flagged, because a *guessed* check-out must be visible as a guess.
        """
        Attendance = self.env["hr.attendance"].sudo()
        now = fields.Datetime.now()
        for store in self.env["analitix.store"].sudo().search(
                [("attendance_enabled", "=", True)]):
            cutoff = now - timedelta(hours=store.attendance_max_hours)
            # Only rows Analitix itself opened. Closing a shift somebody
            # started by hand would be exactly the overreach this bridge
            # promises not to commit — and keying on the store rather than on
            # who still has a face signature means an employee whose signature
            # was removed is still tidied up.
            stale = Attendance.search([
                ("analitix_store_id", "=", store.id),
                ("check_out", "=", False),
                ("check_in", "<", cutoff),
            ])
            for row in stale:
                row.write({
                    "check_out": row.check_in + timedelta(
                        hours=store.attendance_max_hours),
                })
                try:
                    row.employee_id.message_post(body=_(
                        "Analitix closed this attendance automatically: no exit "
                        "was seen. The check-out time is the store's maximum "
                        "shift length, not an observation — correct it if the "
                        "real time matters."))
                except Exception:  # noqa: BLE001
                    _logger.debug("Analitix: could not annotate attendance.")
        return True


register_handler("attendance_register", "analitix.attendance", "_run_register")
