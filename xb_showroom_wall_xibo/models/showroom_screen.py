# -*- coding: utf-8 -*-
"""Putting the showroom wall on a Xibo screen.

The wall is a web page. On a Xibo screen it lives inside a one-widget layout
built on the screen's own canvas, and there are two ways to let it in:

* ``default`` — the layout becomes the screen's default layout. The wall page
  then decides by itself what to show (a piece, a comparison, its own shop
  window), so nothing has to reach the player when a sales person taps: it
  is instant and does not depend on the player's live channel (XMR).
* ``on_demand`` — the screen keeps its own default layout, and the wall is
  put on screen the same way the purchase thank-you is: for a bounded window
  that restarts with every piece sent, and taken off when the wall is cleared.
"""
import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# How long the wall stays on a Xibo screen when the showroom screen never goes
# idle on its own (``idle_timeout`` = 0): long enough for a shift, bounded so
# a forgotten session still hands the screen back.
ON_DEMAND_MAX_SECONDS = 4 * 3600
# Refresh the on-screen window at most this often while pieces keep coming:
# every refresh reschedules the layout, and there is no need to do it per tap.
ON_DEMAND_REFRESH_SECONDS = 60


class ShowroomScreen(models.Model):
    _inherit = 'xb.showroom.screen'

    xibo_pos_config_id = fields.Many2one(
        'pos.config', string='Branch',
        domain="[('xibo_server_id', '!=', False)]",
        help="The point of sale of the branch where this wall hangs. Its Xibo "
             "server is the one the wall is published on.")
    xibo_server_id = fields.Many2one(
        related='xibo_pos_config_id.xibo_server_id', string='Xibo server')
    xibo_display_id = fields.Many2one(
        'xibo.display', string='Xibo screen',
        domain="[('server_id', '=', xibo_server_id)]",
        help="The screen (or videowall) in Xibo that shows this wall. The "
             "layout is built on its canvas, so a 5760x1080 videowall gets "
             "the whole surface.")
    xibo_mode = fields.Selection(
        [('default', 'Always on screen (default layout)'),
         ('on_demand', 'Only while pieces are shown')],
        string='How it enters Xibo', default='default', required=True,
        help="Always on screen: the wall becomes the screen's default layout "
             "and shows its own shop window when idle. Instant.\n"
             "Only while pieces are shown: the screen keeps its own default "
             "layout; the wall takes over when a piece is sent and hands the "
             "screen back when cleared or idle. Relies on the player's live "
             "channel, as the purchase thank-you does.")
    xibo_layout_id = fields.Many2one(
        'xibo.layout', string='Xibo layout', readonly=True, copy=False)
    xibo_layout_url = fields.Char(readonly=True, copy=False)
    xibo_published = fields.Boolean(string='Published on Xibo', readonly=True, copy=False)
    xibo_previous_layout_xibo_id = fields.Integer(
        string='Default layout before', readonly=True, copy=False,
        help="The screen's default layout before the wall replaced it. "
             "Removing the wall puts it back.")
    xibo_previous_layout_name = fields.Char(
        string='Previous default layout', readonly=True, copy=False)
    xibo_on_air_until = fields.Datetime(readonly=True, copy=False)
    xibo_status = fields.Char(compute='_compute_xibo_status', string='Status')

    @api.onchange('xibo_pos_config_id')
    def _onchange_xibo_pos_config_id(self):
        if self.xibo_display_id.server_id != self.xibo_server_id:
            self.xibo_display_id = False

    @api.depends('xibo_published', 'xibo_mode', 'xibo_display_id',
                 'xibo_previous_layout_name', 'xibo_on_air_until')
    def _compute_xibo_status(self):
        for screen in self:
            if not screen.xibo_published:
                screen.xibo_status = _("Not published on Xibo.")
            elif screen.xibo_mode == 'default':
                screen.xibo_status = _(
                    "Default layout of %(screen)s. When removed, it goes back to «%(previous)s».",
                    screen=screen.xibo_display_id.name,
                    previous=screen.xibo_previous_layout_name or _("nothing recorded"))
            elif screen.xibo_on_air_until and screen.xibo_on_air_until > fields.Datetime.now():
                screen.xibo_status = _(
                    "On %(screen)s now, showing pieces. Hands the screen back when cleared or idle.",
                    screen=screen.xibo_display_id.name)
            else:
                screen.xibo_status = _(
                    "Ready on %(screen)s: it takes over when a piece is sent.",
                    screen=screen.xibo_display_id.name)

    # ------------------------------------------------------------------
    # Talking to the CMS
    # ------------------------------------------------------------------
    def _xibo_check(self):
        self.ensure_one()
        if not self.xibo_pos_config_id or not self.xibo_display_id:
            raise UserError(_("Choose the branch and its Xibo screen first."))
        server = self.xibo_server_id
        if not server or server.state != 'connected':
            raise UserError(_("The Xibo server of this branch is not connected."))
        if self.xibo_display_id.server_id != server:
            raise UserError(_("That Xibo screen belongs to another server."))
        if not self.xibo_display_id.xibo_display_id:
            raise UserError(_("That Xibo screen was never synced with the CMS."))
        return server

    def _xibo_background(self):
        """The colour behind the page while it loads, so it never flashes."""
        if self.bg_color and self.bg_color != '#0d0d0f':
            return self.bg_color
        return '#0d0d0f' if (self.theme == 'dark' and self.wall_style != 'mosaic') else '#f7f5f1'

    def _xibo_ensure_layout(self):
        """The published layout showing this wall, (re)built when needed."""
        self.ensure_one()
        config = self.xibo_pos_config_id
        geometry = self.xibo_display_id._layout_geometry()
        reason = config._xibo_layout_status(self.xibo_layout_id, geometry)
        if not reason and self.xibo_layout_url != self.wall_url:
            reason = 'url'   # the wall token was reset since
        if not reason:
            return self.xibo_layout_id
        _logger.info("[SHOWROOM XIBO] building the layout of %s on %s (reason=%s, %sx%s)",
                     self.name, self.xibo_display_id.name, reason,
                     geometry['width'], geometry['height'])
        layout = config._xibo_build_url_layout(
            _("Showroom Wall — %(name)s [%(stamp)s]",
              name=self.name, stamp=fields.Datetime.now().strftime('%Y%m%d-%H%M%S')),
            self.wall_url, geometry,
            widget_name=_("Showroom"), duration=86400,
            background_color=self._xibo_background(),
        )
        self.write({'xibo_layout_id': layout.id, 'xibo_layout_url': self.wall_url})
        return layout

    def _xibo_display_row(self):
        server = self.xibo_server_id
        rows = server._request('GET', '/api/display',
                               params={'displayId': self.xibo_display_id.xibo_display_id},
                               raise_on_error=False)
        return rows[0] if isinstance(rows, list) and rows else {}

    def _xibo_layout_name(self, layout_xibo_id):
        rows = self.xibo_server_id._request('GET', '/api/layout',
                                            params={'layoutId': layout_xibo_id},
                                            raise_on_error=False)
        return (rows[0].get('layout') if isinstance(rows, list) and rows else '') or ''

    def _xibo_set_default_layout(self, layout_xibo_id):
        """Make ``layout_xibo_id`` the screen's default layout and verify it."""
        server = self.xibo_server_id
        display = self.xibo_display_id
        server._request('PUT', '/api/display/defaultlayout/%s' % display.xibo_display_id,
                        data={'layoutId': layout_xibo_id}, raise_on_error=False)
        now_default = self._xibo_display_row().get('defaultLayoutId')
        if now_default != layout_xibo_id:
            raise UserError(_(
                "Xibo did not accept the new default layout for %(screen)s "
                "(it still reports layout %(current)s).",
                screen=display.name, current=now_default))
        if display.own_display_group_id:
            server._trigger_collect_now([display.own_display_group_id])
        return True

    def _xibo_is_ours(self, layout_xibo_id):
        """True when ``layout_xibo_id`` is one of the layouts built for a wall.

        A republished layout gets a new id in Xibo, so the stored record is
        refreshed first; older walls of this screen count as ours too, so
        publishing twice never records the wall itself as "the layout before".
        """
        self.ensure_one()
        if self.xibo_layout_id:
            self.xibo_pos_config_id._xibo_cms_layout(self.xibo_layout_id)
        ours = self.search([
            ('xibo_layout_id', '!=', False),
            ('company_id', '=', self.company_id.id),
        ]).mapped('xibo_layout_id.xibo_layout_id')
        return layout_xibo_id in ours

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def _xibo_check_rights(self):
        """The group is not enough: this screen has to be theirs too.

        Without the record check, a manager of one company could publish or
        unpublish another company's wall by calling the button over RPC with
        a guessed id, since the work that follows runs as superuser.
        """
        if not (self.env.user.has_group('sales_team.group_sale_manager') or self.env.is_admin()):
            raise AccessError(_("Only a sales manager can put the wall on a Xibo screen."))
        self.check_access('write')

    def action_xibo_publish(self):
        self.ensure_one()
        self._xibo_check_rights()
        return self.sudo()._xibo_publish()

    def action_xibo_unpublish(self):
        self.ensure_one()
        self._xibo_check_rights()
        return self.sudo()._xibo_unpublish()

    def _xibo_publish(self):
        self.ensure_one()
        self._xibo_check()
        # Look at the screen BEFORE (re)building: if the wall has to be rebuilt,
        # the old wall layout is still what the screen shows, and it must not be
        # mistaken for the layout to give back later.
        current = self._xibo_display_row().get('defaultLayoutId')
        current_is_ours = bool(current) and self._xibo_is_ours(current)
        layout = self._xibo_ensure_layout()
        vals = {'xibo_published': True}
        if self.xibo_mode == 'default':
            if current and not current_is_ours:
                vals.update({
                    'xibo_previous_layout_xibo_id': current,
                    'xibo_previous_layout_name': self._xibo_layout_name(current),
                })
            if current != layout.xibo_layout_id:
                self._xibo_set_default_layout(layout.xibo_layout_id)
            message = _("The wall is now the default layout of %s.", self.xibo_display_id.name)
        else:
            # Coming from "always on screen": give the screen its layout back.
            if current_is_ours and self.xibo_previous_layout_xibo_id:
                self._xibo_set_default_layout(self.xibo_previous_layout_xibo_id)
                vals.update({'xibo_previous_layout_xibo_id': 0,
                             'xibo_previous_layout_name': False})
            message = _("%s keeps its default layout; the wall takes over when a piece is sent.",
                        self.xibo_display_id.name)
        self.write(vals)
        return self._xibo_notify(message)

    def _xibo_unpublish(self):
        self.ensure_one()
        self._xibo_check()
        self._xibo_go_off_air()
        message = _("The wall is no longer on %s.", self.xibo_display_id.name)
        current = self._xibo_display_row().get('defaultLayoutId')
        if current and self._xibo_is_ours(current):
            if not self.xibo_previous_layout_xibo_id:
                raise UserError(_(
                    "The wall is the default layout of %s and there is no record of what "
                    "was there before. Choose another default layout in Xibo first.",
                    self.xibo_display_id.name))
            self._xibo_set_default_layout(self.xibo_previous_layout_xibo_id)
            message = _("%(screen)s is back on «%(previous)s».",
                        screen=self.xibo_display_id.name,
                        previous=self.xibo_previous_layout_name or self.xibo_previous_layout_xibo_id)
        self.write({'xibo_published': False, 'xibo_previous_layout_xibo_id': 0,
                    'xibo_previous_layout_name': False})
        return self._xibo_notify(message)

    def _xibo_notify(self, message):
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'message': message, 'type': 'success', 'sticky': False,
                       'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}},
        }

    # ------------------------------------------------------------------
    # "Only while pieces are shown"
    # ------------------------------------------------------------------
    def _xibo_purpose(self):
        return 'showroom-wall-%s' % self.id

    def _xibo_window(self):
        return min((self.idle_timeout or 0) * 60 or ON_DEMAND_MAX_SECONDS, ON_DEMAND_MAX_SECONDS)

    def _xibo_go_on_air(self):
        """Put the wall on its Xibo screen for the next idle window."""
        self.ensure_one()
        if not (self.xibo_published and self.xibo_mode == 'on_demand' and self.xibo_layout_id):
            return False
        now = fields.Datetime.now()
        window = self._xibo_window()
        if self.xibo_on_air_until:
            left = (self.xibo_on_air_until - now).total_seconds()
            if left > window - ON_DEMAND_REFRESH_SECONDS:
                return True   # refreshed less than a minute ago
        self.xibo_pos_config_id._xibo_show_on_screen(
            self.xibo_display_id, self.xibo_layout_id, window,
            self._xibo_purpose(), mode='replace')
        self.xibo_on_air_until = fields.Datetime.add(now, seconds=window)
        return True

    def _xibo_go_off_air(self, revert=True):
        """Hand the Xibo screen back to its own schedule."""
        self.ensure_one()
        if not self.xibo_on_air_until:
            return False
        config = self.xibo_pos_config_id
        display = self.xibo_display_id
        self.xibo_on_air_until = False
        config._xibo_drop_schedule(self._xibo_purpose())
        if revert and display.own_display_group_id:
            if display.force_schedule:
                config.xibo_server_id._trigger_collect_now([display.own_display_group_id])
            config.xibo_server_id.revert_layout(display.own_display_group_id)
        return True

    def _xibo_safely(self, method):
        """Xibo trouble must never cost the sales person the wall itself."""
        for screen in self:
            if not (screen.xibo_published and screen.xibo_mode == 'on_demand'):
                continue
            try:
                getattr(screen, method)()
            except Exception as e:
                _logger.warning("[SHOWROOM XIBO] %s failed for %s: %s", method, screen.name, e)

    def _push_entries(self, entries, mode='single'):
        result = super()._push_entries(entries, mode=mode)
        self._xibo_safely('_xibo_go_on_air')
        return result

    def action_clear(self):
        result = super().action_clear()
        self._xibo_safely('_xibo_go_off_air')
        return result
