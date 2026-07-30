# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

# Grace period before an expired entry is removed from the CMS. The player
# compares the window against its own clock, so deleting the event the very
# second it lapses can cut the content short on a screen that runs a little
# behind.
GC_GRACE_SECONDS = 120


class XiboScheduleEvent(models.Model):
    """Schedule entries Odoo created on the CMS and must clean up itself.

    Content Odoo shows for a moment — a cart mirror, a thank-you message — is
    normally pushed over XMR and never touches the schedule. Players that
    ignore those pushes need the content scheduled instead, and a schedule
    entry, unlike a push, stays behind. This model remembers every entry we
    create so the CMS does not slowly fill up with dead events.
    """
    _name = 'xibo.schedule.event'
    _description = 'Xibo Temporary Schedule Entry'
    _order = 'expires_at'

    server_id = fields.Many2one('xibo.server', required=True, ondelete='cascade', index=True)
    xibo_event_id = fields.Integer(string='Xibo Event ID', required=True, index=True)
    display_group_xibo_id = fields.Integer(string='Xibo Display Group ID')
    layout_name = fields.Char(string='Layout')
    purpose = fields.Char(
        help="What this entry was created for, so a leftover event can be "
             "traced back to the feature that made it.",
    )
    expires_at = fields.Datetime(
        required=True, index=True,
        help="When the scheduled window ends. The clean-up job deletes the "
             "entry from the CMS shortly after.",
    )

    @api.model
    def track(self, server, event_id, display_group_xibo_id=None,
              expires_at=None, purpose=None, layout_name=None):
        """Record an event we created on the CMS. Returns the new record."""
        return self.sudo().create({
            'server_id': server.id,
            'xibo_event_id': event_id,
            'display_group_xibo_id': display_group_xibo_id or 0,
            'expires_at': expires_at or fields.Datetime.now(),
            'purpose': purpose or '',
            'layout_name': layout_name or '',
        })

    def drop(self):
        """Delete these entries from the CMS and forget them.

        A CMS-side failure still drops the Odoo record: the event either no
        longer exists (someone removed it by hand) or is unreachable, and
        keeping a row that we retry forever helps nobody. The window is
        bounded anyway, so a stranded event stops playing on its own.
        """
        for rec in self.sudo():
            if rec.server_id and rec.xibo_event_id:
                rec.server_id.delete_schedule_event(rec.xibo_event_id)
        self.sudo().unlink()
        return True

    @api.model
    def _gc_expired(self):
        """Cron: remove entries whose window has passed."""
        deadline = fields.Datetime.now() - timedelta(seconds=GC_GRACE_SECONDS)
        stale = self.sudo().search([('expires_at', '<=', deadline)])
        if stale:
            _logger.info("Xibo: cleaning up %s expired schedule entries", len(stale))
            stale.drop()
        return True
