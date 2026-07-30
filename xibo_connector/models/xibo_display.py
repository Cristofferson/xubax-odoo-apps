# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class XiboDisplay(models.Model):
    _name = 'xibo.display'
    _description = 'Xibo Display / Player'
    _inherit = ['mail.thread']
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(string='Display Name', required=True, tracking=True)
    server_id = fields.Many2one('xibo.server', required=True, ondelete='cascade', tracking=True)
    xibo_display_id = fields.Integer(string='Xibo Display ID', readonly=True, copy=False)
    own_display_group_id = fields.Integer(
        string='Own Display Group ID', readonly=True, copy=False,
        help="Xibo creates a display-specific group per display, used as the XMR channel.",
    )
    license_code = fields.Char(string='License Code', readonly=True)
    logged_in = fields.Boolean(string='Online in Xibo', readonly=True)
    last_accessed = fields.Datetime(string='Last Accessed', readonly=True)
    client_type = fields.Char(string='Player Type', readonly=True)
    # ---- Screen geometry (since v19.0.1.6.3) ----
    # Reported by the player itself and mirrored here so layouts can be
    # created with the RIGHT canvas instead of a hard-coded landscape one.
    orientation = fields.Char(
        string='Orientation', readonly=True,
        help="Screen orientation reported by the player (landscape / portrait).",
    )
    resolution = fields.Char(
        string='Screen Resolution', readonly=True,
        help="Native resolution reported by the player, e.g. 1080x1920.",
    )
    resolution_xibo_id = fields.Integer(
        string='Xibo Resolution ID', readonly=True, copy=False,
        help="Id of the CMS resolution that matches this screen. Used as "
             "`resolutionId` when this module creates layouts for the "
             "display, so a portrait screen gets a portrait layout.",
    )
    # Canvas of the matched CMS resolution — NOT the raw size the player
    # reports. Regions must be laid out on the canvas the layout actually
    # uses, and the two differ whenever the exact screen size has no
    # matching resolution in the CMS.
    resolution_width = fields.Integer(string='Canvas Width', readonly=True)
    resolution_height = fields.Integer(string='Canvas Height', readonly=True)
    # ---- Stubborn players (since v19.0.1.6.4) ----
    force_schedule = fields.Boolean(
        string='Player Ignores Instant Changes', tracking=True,
        help="Tick this when the screen never reacts to content Odoo pushes "
             "in real time, even though the CMS accepts the order. Some "
             "players only ever play what is on their schedule. Odoo then "
             "schedules the content for the moment it is needed and removes "
             "the entry afterwards, instead of relying on the instant push "
             "alone.",
    )
    description = fields.Text()
    active = fields.Boolean(default=True, tracking=True)
    purpose = fields.Selection(
        [('reception', 'Reception / Welcome'),
         ('promo', 'Promotions'),
         ('info', 'Information / News'),
         ('mixed', 'Mixed Use')],
        default='mixed',
    )
    group_ids = fields.Many2many(
        'xibo.display.group', 'xibo_display_group_display_rel',
        'display_id', 'group_id', string='Groups',
    )
    company_id = fields.Many2one(related='server_id.company_id', store=True)

    _sql_constraints = [
        ('xibo_id_unique', 'unique(server_id, xibo_display_id)',
         'This Xibo display is already registered for this server.'),
    ]

    @api.model
    def _sync_from_server(self, server):
        payload = server._request('GET', '/api/display')
        if not isinstance(payload, list):
            return False
        existing = {d.xibo_display_id: d
                    for d in self.search([('server_id', '=', server.id)])}
        # Resolution catalogue of the CMS — fetched once per sync so every
        # display can be matched to a real resolutionId without an extra
        # round-trip later (layout creation is on the POS hot path).
        catalogue = server._resolution_catalogue()
        for entry in payload:
            xid = entry.get('displayId')
            if not xid:
                continue
            resolution = entry.get('resolution') or ''
            geometry = server._match_resolution(
                resolution, entry.get('orientation'), catalogue=catalogue,
            )
            values = {
                'name': entry.get('display') or _('Unnamed display'),
                'server_id': server.id,
                'xibo_display_id': xid,
                'own_display_group_id': entry.get('displayGroupId') or 0,
                'license_code': entry.get('license'),
                'logged_in': bool(entry.get('loggedIn')),
                'client_type': entry.get('clientType'),
                'last_accessed': self._parse_xibo_dt(entry.get('lastAccessed')),
                'orientation': entry.get('orientation') or '',
                'resolution': resolution,
                'resolution_xibo_id': geometry['resolution_id'],
                'resolution_width': geometry['width'],
                'resolution_height': geometry['height'],
            }
            if xid in existing:
                existing[xid].write(values)
            else:
                self.create(values)
        _logger.info("Xibo: synced %s displays for %s", len(payload), server.name)
        return True

    def _layout_geometry(self):
        """Return the canvas a layout aimed at this display must use.

        ``{'resolution_id': int, 'width': int, 'height': int}``

        Falls back to 1080p landscape when the screen geometry is unknown
        (display never synced with a version that stores it, or a player
        that does not report its resolution). When the display was synced
        before v19.0.1.6.3 the match is resolved lazily and stored, so the
        extra API call happens at most once per display.
        """
        fallback = {'resolution_id': 1, 'width': 1920, 'height': 1080}
        if not self:
            return fallback
        self.ensure_one()
        if self.resolution_xibo_id and self.resolution_width and self.resolution_height:
            return {
                'resolution_id': self.resolution_xibo_id,
                'width': self.resolution_width,
                'height': self.resolution_height,
            }
        # Display synced by an older version (or never synced since the
        # player reported its screen): resolve once and remember it.
        if not self.server_id:
            return fallback
        geometry = self.server_id._match_resolution(
            self.resolution, self.orientation,
        )
        try:
            self.sudo().write({
                'resolution_xibo_id': geometry['resolution_id'],
                'resolution_width': geometry['width'],
                'resolution_height': geometry['height'],
            })
        except Exception as e:
            _logger.warning(
                "Xibo: could not store the resolution of display %s: %s",
                self.display_name, e)
        return geometry

    @staticmethod
    def _parse_xibo_dt(value):
        if not value:
            return False
        try:
            return fields.Datetime.to_datetime(value)
        except Exception:
            return False

    def action_refresh(self):
        for srv in self.mapped('server_id'):
            self._sync_from_server(srv)
        return True

    def action_collect_now(self):
        for rec in self:
            if rec.own_display_group_id:
                rec.server_id._trigger_collect_now([rec.own_display_group_id])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Refresh sent"),
                'message': _("XMR collectNow dispatched to %s display(s).") % len(self),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_open_in_cms(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f"{self.server_id.url}/display/view",
            'target': 'new',
        }
