# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _xibo_activate_thanks_layout(self, order, message, ctx=None):
        """A sale closes the showroom session on the same screen.

        A wall shown "only while pieces are shown" lives in the screen's
        schedule. Left there, the player would alternate between it and the
        thank-you, or come back to the wall once the thank-you ends. The
        thank-you replaces what is on screen and, when it ends, the player
        falls back to its own default layout, which is what the shop expects
        after a sale.
        """
        screens = self.env['xb.showroom.screen'].sudo().search([
            ('xibo_mode', '=', 'on_demand'),
            ('xibo_on_air_until', '!=', False),
            ('xibo_display_id', 'in', self.xibo_thanks_display_ids.ids),
        ])
        for screen in screens:
            try:
                screen._xibo_go_off_air(revert=False)
            except Exception as e:  # never cost the customer their thank-you
                _logger.warning("[SHOWROOM XIBO] could not hand %s over to the thank-you: %s",
                                screen.name, e)
        return super()._xibo_activate_thanks_layout(order, message, ctx=ctx)
