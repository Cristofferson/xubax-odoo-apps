# -*- coding: utf-8 -*-
from odoo import fields, http, _
from odoo.http import request

from odoo.addons.xb_showroom_wall.controllers.wall import _from_price, _may_show

# Seconds a piece a customer sent stays before the same wall takes another
# one from a kiosk. A sales person's push is never held back. Comparing adds
# pieces on purpose one after the other, so it is not held back either.
KIOSK_PAUSE = 5


class ShowroomKiosk(http.Controller):

    def _kiosk_screen(self, access_token):
        """``(config, screen)`` of the kiosk proving itself with its point of
        sale's access token, exactly like the orders it sends; empty if not."""
        Screen = request.env['xb.showroom.screen']
        if not access_token or not isinstance(access_token, str):
            return None, Screen
        config = request.env['pos.config'].sudo().search(
            [('access_token', '=', access_token)], limit=1)
        if not config or not config.has_active_session:
            return config, Screen
        return config, config._xb_showroom_kiosk_screen()

    def _kiosk_amount(self, screen, template, options):
        """The figure the wall shows, priced like the shop does: the chosen
        options (what is missing takes the cheapest gold, as the kiosk shows
        it), or the shop's «from» figure when nothing was chosen."""
        if screen.show_price == 'none':
            return None
        try:
            if not options:
                return _from_price(template)
            if hasattr(template, '_xb_combinacion_desde'):
                base = template._xb_combinacion_desde()
            else:
                base = template._get_first_possible_combination()
            comb = base.filtered(lambda v: v.attribute_line_id not in options.attribute_line_id) | options
            return template._get_combination_info(comb).get('price') or None
        except Exception:  # noqa: BLE001 - a price must never stop the push
            return None

    def _kiosk_pieces(self, screen):
        """The pieces the kiosk is comparing on the wall, for its bar."""
        if not screen or screen.mode != 'compare':
            return []
        return [{
            'slot_id': slot.id,
            'template_id': slot.product_id.product_tmpl_id.id,
            'options': slot.option_ids.ids,
            'name': slot.product_id.product_tmpl_id.name,
            'image': '/web/image/product.template/%s/image_128' % slot.product_id.product_tmpl_id.id,
        } for slot in screen.sudo().slot_ids.filtered(lambda s: s.source == 'kiosk')]

    def _kiosk_state(self, screen, **extra):
        return dict(extra, pieces=self._kiosk_pieces(screen),
                    limit=screen.sudo()._compare_limit() if screen else 0)

    @http.route('/xb_showroom/kiosk/push', type='jsonrpc', auth='public', website=True)
    def kiosk_push(self, access_token=None, template_id=None, combination=None, mode='single', **kw):
        """A customer asks for a piece on the wall from the kiosk, alone or
        joining the comparison (the same rules as the shop's «Compare»)."""
        not_now = {'error': _("The wall is not available from this kiosk right now.")}
        config, screen = self._kiosk_screen(access_token)
        if not screen:
            return not_now
        mode = 'compare' if mode == 'compare' else 'single'
        try:
            template = request.env['product.template'].sudo().browse(int(template_id or 0)).exists()
            options = request.env['product.template.attribute.value'].sudo().browse(
                [int(value) for value in (combination or []) if value]).exists()
        except (TypeError, ValueError):
            return {'error': _("Could not tell which piece to show.")}
        if (not template or not template.xb_showroom_enabled
                or not template.available_in_pos or not template.self_order_available
                or not _may_show(screen, template)):
            return {'error': _("This piece cannot be shown on the wall.")}
        if mode == 'single' and screen.mode == 'single':
            # Only between single pieces: right after comparing, a single piece
            # is a new request that replaces the comparison, as in the shop.
            last = screen.slot_ids.filtered(lambda s: s.source == 'kiosk')[:1]
            if last and (fields.Datetime.now() - last.create_date).total_seconds() < KIOSK_PAUSE:
                return {'error': _("One moment: the wall is showing the piece that was just sent."),
                        'wait': True}
        options = options.filtered(lambda v: v.product_tmpl_id == template)
        product = (template._get_variant_for_combination(options) if options else None) \
            or template.product_variant_id
        if not product:
            return {'error': _("This piece cannot be shown on the wall.")}
        amount = self._kiosk_amount(screen, template, options)
        currency = request.website.currency_id if request.website else product.currency_id
        entry = {'product': product, 'options': options, 'price': amount,
                 'currency': currency if amount is not None else None}
        entries = [entry]
        repeated = False
        if mode == 'compare':
            # As in the shop: what is on the wall stays and the new piece joins
            # at the end; the same ring sent again moves to the end. Only the
            # kiosk's own pieces are kept: a sales person's push gave way.
            own = screen.slot_ids.filtered(lambda s: s.source == 'kiosk') \
                if screen.mode == 'compare' else screen.slot_ids.browse()
            already = own.filtered(
                lambda s: s.product_id.product_tmpl_id == template and (
                    not options or not s.option_ids
                    or set(s.option_ids.ids) == set(options.ids)))
            repeated = bool(already)
            entries = [
                {'product': slot.product_id, 'options': slot.option_ids,
                 'price': slot.price, 'currency': slot.currency_id}
                for slot in own - already
            ] + [entry]
        result = screen.sudo().with_context(xb_showroom_source='kiosk')._push_entries(entries, mode=mode)
        message = _("Look at the wall!")
        if mode == 'compare':
            message = _("On the wall: comparing %s.", result['count'])
            if repeated:
                message = _("That piece was already on the wall; it moved to the end.")
            if result['dropped']:
                message = _("The wall holds %(max)s pieces: %(names)s was taken off to make room.",
                            max=result['limit'],
                            names=', '.join(p.product_tmpl_id.name for p in result['dropped']))
        return self._kiosk_state(screen, ok=True, mode=mode, message=message)

    @http.route('/xb_showroom/kiosk/state', type='jsonrpc', auth='public', website=True)
    def kiosk_state(self, access_token=None, **kw):
        """What the kiosk is comparing on the wall right now."""
        config, screen = self._kiosk_screen(access_token)
        return self._kiosk_state(screen, ok=bool(screen))

    @http.route('/xb_showroom/kiosk/remove', type='jsonrpc', auth='public', website=True)
    def kiosk_remove(self, access_token=None, slot_id=None, **kw):
        """Take one of the kiosk's pieces off the wall; the others stay."""
        config, screen = self._kiosk_screen(access_token)
        if not screen:
            return {'error': _("The wall is not available from this kiosk right now.")}
        try:
            slot_id = int(slot_id or 0)
        except (TypeError, ValueError):
            slot_id = 0
        mine = screen.sudo().slot_ids.filtered(lambda s: s.id == slot_id and s.source == 'kiosk')
        removed = bool(mine) and screen.sudo()._remove_slot(slot_id)
        return self._kiosk_state(screen, ok=bool(removed))

    @http.route('/xb_showroom/kiosk/clear', type='jsonrpc', auth='public', website=True)
    def kiosk_clear(self, access_token=None, **kw):
        """New comparison: the wall goes back to its shop window, but only if
        what it shows came from the kiosk (never a sales person's pieces)."""
        config, screen = self._kiosk_screen(access_token)
        if not screen:
            return {'error': _("The wall is not available from this kiosk right now.")}
        slots = screen.sudo().slot_ids
        if slots and all(s.source == 'kiosk' for s in slots):
            screen.sudo().action_clear()
        return self._kiosk_state(screen, ok=True)
