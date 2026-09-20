# -*- coding: utf-8 -*-
"""The wall page, its state feed, and the tablet's push endpoint.

The wall is a plain public URL that polls ``/state``: no live command has to
reach the signage player, so a player that only checks in every few minutes
still shows the piece instantly.
"""
import base64
import io
import json
import logging

from odoo import http, _
from odoo.http import request, Response
from odoo.tools import float_round

_logger = logging.getLogger(__name__)

# Groups allowed to drive a showroom screen from the shop.
PUSH_GROUPS = ('sales_team.group_sale_salesman', 'point_of_sale.group_pos_user')

# Matches the field default; anything else counts as a deliberate override.
DEFAULT_BG = '#0d0d0f'


def _screen(token):
    """Public lookup of a screen by its secret token."""
    if not token:
        return request.env['xb.showroom.screen']
    return request.env['xb.showroom.screen'].sudo().search(
        [('access_token', '=', token)], limit=1)


def _has_group(user, xmlid):
    """``has_group`` on a group that may not be installed."""
    try:
        return user.has_group(xmlid)
    except ValueError:
        return False


def _may_push(user):
    if user.share or user._is_public():
        return False
    return (any(_has_group(user, g) for g in PUSH_GROUPS)
            or _has_group(user, 'base.group_system'))


def _video_url(product):
    """URL of the product's own mp4, if one was published on it."""
    attachment = request.env['ir.attachment'].sudo().search([
        ('res_model', '=', 'product.template'),
        ('res_id', '=', product.product_tmpl_id.id),
        ('mimetype', 'in', ('video/mp4', 'video/webm')),
        ('public', '=', True),
    ], order='id desc', limit=1)
    return '/web/content/%s' % attachment.id if attachment else ''


def _studio_background(product):
    """The photo's own backdrop colour, so the wall can blend into it.

    Catalogue shots are taken on a light studio backdrop, and a plain dark
    wall shows the edge of the picture as a bright rectangle. Sampling the
    corner makes the frame disappear. Anything that is not a light backdrop
    is ignored, so lifestyle photography keeps the configured theme.
    """
    raw = product.image_128 or product.product_tmpl_id.image_128
    if not raw:
        return ''
    try:
        from PIL import Image
        image = Image.open(io.BytesIO(base64.b64decode(raw))).convert('RGB')
        patch = image.crop((1, 1, 10, 10)).resize((1, 1))
        red, green, blue = patch.getpixel((0, 0))
    except Exception as e:  # pragma: no cover - never break the wall for this
        _logger.debug("[SHOWROOM] could not sample the backdrop: %s", e)
        return ''
    luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255
    if luminance < 0.82:
        return ''
    return '#%02x%02x%02x' % (red, green, blue)


# The catalogue keeps one shot of the piece in its case and one on a hand,
# named in Spanish or English. Matching the name is what makes them land on
# the right panel; when a shop names them differently the sequence decides,
# because the case is always photographed before the hand.
_CASE_WORDS = ('estuche', 'caja', 'case', 'box')
_HAND_WORDS = ('mano', 'dedo', 'hand', 'finger')


def _extra_shots(product):
    """``{'case': url, 'hand': url}`` from the product's extra images."""
    images = product.product_tmpl_id.sudo().product_template_image_ids
    shots = {}
    leftovers = []
    for image in images.sorted(lambda i: (i.sequence, i.id)):
        label = (image.name or '').strip().lower()
        url = '/web/image/product.image/%s/image_1024' % image.id
        if any(word in label for word in _CASE_WORDS):
            shots.setdefault('case', url)
        elif any(word in label for word in _HAND_WORDS):
            shots.setdefault('hand', url)
        else:
            leftovers.append(url)
    for key in ('case', 'hand'):
        if key not in shots and leftovers:
            shots[key] = leftovers.pop(0)
    return shots


_METAL_WORDS = ('metal', 'material')


def _is_metal(label):
    return (label or '').strip().lower() in _METAL_WORDS


def _metal(product):
    """The metal, which the wall shows as the headline's second line."""
    return next((value for label, value in _specs(product) if _is_metal(label)), '')


# Commercial names are written as «Verona · Solitario catedral con pavé»: a
# name to remember and, after the separator, what the piece is. The wall gives
# each half its own line instead of cramming both into the big one.
_NAME_SEPARATORS = ('·', '—', '|')


def _split_name(name):
    """``('Verona', 'Solitario catedral con pavé')``, or ``(name, '')``."""
    for separator in _NAME_SEPARATORS:
        head, found, tail = (name or '').partition(separator)
        if found and head.strip() and tail.strip():
            return head.strip(), tail.strip()
    return (name or '').strip(), ''


def _metal_label(options, screen):
    """What the shop calls the metal, for the data line."""
    if options:
        for label, _value in _option_specs(options):
            if _is_metal(label):
                return label
    return screen.env._("Metal")


def _headline(screen, product):
    """The big line. A reference like «MONTADURA 96-0-01-18-0-02» reads badly
    across a shop, so the screen can build the line from the data instead
    until the commercial names are written."""
    template = product.product_tmpl_id
    if screen.title_mode == 'category':
        return (template.public_categ_ids[:1].name
                or template.categ_id.name or template.name)
    return template.name


def _specs(product):
    """The variant's attribute values, as ``('Metal', 'White gold 14Kt')``."""
    return [
        (ptav.attribute_id.name, ptav.name)
        for ptav in product.product_template_attribute_value_ids
    ]


def _option_specs(options):
    """The options picked on the tablet, in the order the shop lists them."""
    options = options.sorted(lambda v: (v.attribute_line_id.sequence,
                                        v.attribute_id.sequence, v.attribute_id.id))
    return [(value.attribute_id.name, value.name) for value in options]


def _numeric(text):
    try:
        return float(str(text).replace(',', '.'))
    except (TypeError, ValueError):
        return None


def _open_specs(env, product):
    """What can be said of a piece whose options nobody chose yet.

    Sent from the catalogue grid (or rotating in the shop window) a piece has
    no metal or size picked: its "first" variant is just whichever the shop
    happened to create first, so quoting its values would put «yellow gold»
    under a white-gold photo. Only what is true for every version is stated;
    the rest reads as a range or a number of options.
    """
    specs = []
    metal = ''
    metal_count = 0
    for line in product.product_tmpl_id.attribute_line_ids.sorted('sequence'):
        values = line.product_template_value_ids.filtered('ptav_active')
        label = line.attribute_id.name
        if len(values) == 1:
            if _is_metal(label):
                metal = values.name
            else:
                specs.append((label, values.name))
            continue
        if not values:
            continue
        if _is_metal(label):
            metal = env._("Available in %s metals", len(values))
            metal_count = len(values)
            continue
        numbers = [_numeric(v.name) for v in values]
        if all(n is not None for n in numbers):
            low = values[numbers.index(min(numbers))].name
            high = values[numbers.index(max(numbers))].name
            specs.append((label, '%s – %s' % (low, high)))
        else:
            specs.append((label, env._("%s options", len(values))))
    return metal, metal_count, specs


def _price_label(screen, slot):
    if screen.show_price == 'none' or not slot.price:
        return ''
    currency = slot.currency_id or screen.company_id.currency_id
    amount = slot.price
    if screen.show_price == 'from':
        # A deliberately vague figure: round down to a readable step.
        step = 1000 if amount >= 10000 else 100
        amount = float_round(amount, precision_rounding=step, rounding_method='DOWN')
        return screen.env._("From %s") % _money(amount, currency)
    return _money(amount, currency)


def _qr_response(target):
    """A QR png for ``target``, cached: it only changes when the URL does."""
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=10, border=2,
                           error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(target or '')
        qr.make(fit=True)
        buf = io.BytesIO()
        qr.make_image(fill_color='black', back_color='white').save(buf, format='PNG')
    except Exception as e:  # pragma: no cover - qrcode ships with Odoo
        _logger.warning("[SHOWROOM] QR generation failed: %s", e)
        return Response(status=500)
    return Response(buf.getvalue(), headers=[
        ('Content-Type', 'image/png'),
        ('Cache-Control', 'public, max-age=3600'),
    ])


def _idle_price(screen, product):
    """Price label for a piece in the rotation (no push carried its figure)."""
    if screen.show_price == 'none':
        return ''
    currency = product.currency_id or screen.company_id.currency_id
    amount = product.list_price
    if screen.show_price == 'from':
        step = 1000 if amount >= 10000 else 100
        amount = float_round(amount, precision_rounding=step, rounding_method='DOWN')
        return screen.env._("From %s") % _money(amount, currency)
    return _money(amount, currency)


def _money(amount, currency):
    text = '{:,.0f}'.format(amount or 0.0)
    if currency and currency.position == 'after':
        return '%s %s' % (text, currency.symbol or '')
    return '%s%s' % ((currency.symbol or '') if currency else '', text)


class ShowroomWall(http.Controller):

    # ------------------------------------------------------------------
    # The wall itself
    # ------------------------------------------------------------------
    @http.route('/showroom/wall/<string:token>', type='http', auth='public',
                methods=['GET'], csrf=False, save_session=False, sitemap=False)
    def wall(self, token, **kw):
        screen = _screen(token)
        if not screen:
            return Response(_("Unknown showroom screen."), status=404)
        config = {
            'token': token,
            'theme': screen.theme or 'light',
            'style': screen.wall_style or 'mosaic',
            'panels': max(min(screen.panels, 3), 1),
            'poll': max(screen.poll_interval, 1),
            'accent': screen.accent_color or '#cda349',
            # Only pass a background when it is a deliberate override: the
            # theme in the stylesheet handles the usual light/dark case.
            'background': (screen.bg_color or '')
                          if screen.bg_color not in ('', False, DEFAULT_BG) else '',
        }
        logo = ''
        if screen.company_id.logo:
            logo = '/web/image/res.company/%s/logo' % screen.company_id.id
        html = """<!DOCTYPE html>
<html lang="%(lang)s"><head><meta charset="utf-8"/>
<title>%(title)s</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="robots" content="noindex, nofollow"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;1,400&amp;family=Jost:wght@300;400;500&amp;display=swap"/>
<link rel="stylesheet" href="/xb_showroom_wall/static/src/wall/wall.css"/>
</head><body data-logo="%(logo)s" data-theme="%(theme)s" data-style="%(style)s">
<div id="wall" class="wall"></div>
<iframe id="idle" class="idle" referrerpolicy="no-referrer"></iframe>
<script id="cfg" type="application/json">%(config)s</script>
<script src="/xb_showroom_wall/static/src/wall/wall.js" defer></script>
</body></html>""" % {
            'lang': (screen._lang() or 'es').split('_')[0],
            'theme': screen.theme or 'light',
            'style': screen.wall_style or 'mosaic',
            'title': screen.name or 'Showroom',
            'logo': logo,
            'config': json.dumps(config),
        }
        return Response(html, headers=[
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
        ])

    @http.route('/showroom/wall/<string:token>/state', type='http', auth='public',
                methods=['GET'], csrf=False, save_session=False, sitemap=False)
    def wall_state(self, token, **kw):
        screen = _screen(token)
        if not screen:
            return Response('{"error":"unknown"}', status=404,
                            headers=[('Content-Type', 'application/json')])
        state = self._state_dict(screen)
        return Response(json.dumps(state), headers=[
            ('Content-Type', 'application/json; charset=utf-8'),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
        ])

    def _piece_dict(self, screen, product, base, price='', qr=None,
                    options=None, slot=None):
        """One piece as the wall needs it. Shared by the live push and the
        idle rotation so both look identical on screen.

        ``options`` are the attribute values chosen on the tablet. Without
        them the piece is described "open": what holds for every version.
        """
        if options:
            chosen = _option_specs(options)
            metal = next((value for label, value in chosen if _is_metal(label)), '')
            specs = [(label, value) for label, value in chosen if not _is_metal(label)]
            metal_count = 0
        else:
            metal, metal_count, specs = _open_specs(screen.env, product)
        # A commercial name carries its own second line, so the metal moves
        # down to the data line instead of being dropped.
        name, description = _split_name(_headline(screen, product))
        subtitle = description or metal
        if description and metal:
            # «METAL: Disponible en 13 metales» reads twice; on the data line
            # the count on its own is enough.
            value = screen.env._("%s options", metal_count) if metal_count else metal
            specs = [(_metal_label(options, screen), value)] + specs
        return {
            'id': product.id,
            'slot': slot.id if slot else False,
            'name': name,
            # The short commercial name distinguishes pieces when comparing.
            # With the category as the headline they would all read the same,
            # so the reference stays the one that tells them apart.
            'short': name if screen.title_mode == 'product_name' else '',
            'subtitle': subtitle,
            # True when the second line is the description and the metal went
            # down to the data line: the comparison table must not ask for it
            # twice.
            'metal_in_specs': bool(description and metal),
            'product_name': product.product_tmpl_id.name,
            'variant': ', '.join(value for _label, value in ([('', metal)] if metal else []) + specs),
            'specs': [{'label': label, 'value': value} for label, value in specs],
            'reference': product.default_code or product.product_tmpl_id.default_code or '',
            'price': price,
            'image': '/web/image/product.product/%s/image_1920' % product.id,
            'ring': '/web/image/product.product/%s/image_1024' % product.id,
            'video': _video_url(product),
            'shots': _extra_shots(product),
            'bg': _studio_background(product)
                  if (screen.theme == 'light' or screen.wall_style == 'mosaic') else '',
            'qr': qr if qr is not None else (
                '/showroom/wall/%s/qr/%s.png' % (screen.access_token, product.id)),
            'url': '%s%s' % (base.rstrip('/'), product.product_tmpl_id.website_url or ''),
        }

    def _state_dict(self, screen):
        base = request.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        # A public request carries no language, so the wall would fall back to
        # English attribute names in front of the customer.
        screen = screen.with_context(lang=screen._lang())
        env = screen.env
        if not screen._is_live():
            state = {
                'live': False,
                'rev': 'idle-%s' % (screen.idle_mode or 'plain'),
                'idle_mode': screen.idle_mode or 'plain',
                'idle_url': screen.idle_url or '',
                'heading': screen.heading or '',
                'interval': max(screen.idle_interval or 9, 2),
                'pieces': [],
            }
            if screen.idle_mode == 'own':
                qr = '/showroom/wall/%s/qr.png' % screen.access_token
                pieces = [
                    self._piece_dict(screen, product, base,
                                     price=_idle_price(screen, product), qr=qr)
                    for product in screen._idle_pieces()
                ]
                state['pieces'] = pieces
                # The QR caption doubles as the shop window's invitation.
                state['qr_text'] = screen.heading or env._(
                    "Scan to browse the collection")
                state['worn_text'] = env._("How it looks on")
                state['case_text'] = env._("In its case")
                state['rev'] = 'idle-own-%s' % ','.join(
                    str(piece['id']) for piece in pieces)
            return state
        pieces = [
            self._piece_dict(screen, slot.product_id, base,
                             price=_price_label(screen, slot),
                             options=slot.option_ids, slot=slot)
            for slot in screen.slot_ids
        ]
        return {
            'live': True,
            'qr_text': env._("Scan to take this piece with you"),
            'worn_text': env._("How it looks on"),
            'case_text': env._("In its case"),
            'diff_text': env._("Side by side"),
            'price_text': env._("Price"),
            'metal_text': env._("Metal"),
            'rev': '%s-%s-%s' % (
                screen.mode, screen.spotlight_at, ','.join(str(p['slot']) for p in pieces)),
            'mode': screen.mode,
            'heading': screen.heading or '',
            'pieces': pieces,
        }

    @http.route('/showroom/wall/<string:token>/qr.png',
                type='http', auth='public', methods=['GET'], csrf=False,
                save_session=False, sitemap=False)
    def wall_qr_idle(self, token, **kw):
        """QR of the shop window: it invites, it does not point at one piece."""
        screen = _screen(token)
        if not screen:
            return Response(status=404)
        base = (request.env['ir.config_parameter'].sudo()
                .get_param('web.base.url') or '').rstrip('/')
        target = screen.idle_qr_url or '%s/shop' % base
        return _qr_response(target)

    @http.route('/showroom/wall/<string:token>/qr/<int:product_id>.png',
                type='http', auth='public', methods=['GET'], csrf=False,
                save_session=False, sitemap=False)
    def wall_qr(self, token, product_id, **kw):
        """QR of the product page, so the customer can take the piece home."""
        screen = _screen(token)
        if not screen:
            return Response(status=404)
        product = request.env['product.product'].sudo().browse(product_id).exists()
        if not product:
            return Response(status=404)
        base = (request.env['ir.config_parameter'].sudo()
                .get_param('web.base.url') or '').rstrip('/')
        target = '%s%s' % (base, product.product_tmpl_id.website_url or '/shop')
        return _qr_response(target)

    # ------------------------------------------------------------------
    # The tablet
    # ------------------------------------------------------------------
    @http.route('/showroom/push', type='jsonrpc', auth='user', website=True)
    def push(self, product_id=None, template_id=None, combination=None,
             screen_id=None, mode='single', price=None, **kw):
        """Called from the shop by a signed-in sales person.

        From a product page the tablet sends the options the customer picked
        (``combination``, attribute value ids): with dynamic variants that
        exact version usually has no product yet, and the page then reports
        ``product_id`` 0. From a catalogue tile only the template is known.
        """
        user = request.env.user
        if not _may_push(user):
            return {'error': _("You are not allowed to drive the showroom screen.")}
        screen, error = self._pick_screen(screen_id)
        if error:
            return {'error': error}
        env = request.env
        template = env['product.template'].sudo().browse(int(template_id or 0)).exists()
        product = env['product.product'].sudo().browse(int(product_id or 0)).exists()
        if product:
            template = product.product_tmpl_id
        options = env['product.template.attribute.value'].sudo()
        if template and combination:
            options = options.browse([int(i) for i in combination if i]).exists().filtered(
                lambda v: v.product_tmpl_id == template)
        if not product and template:
            product = (template._get_variant_for_combination(options) if options else None) \
                or template.product_variant_id
        if not product:
            return {'error': _("That piece no longer exists.")}
        if not options and product_id:
            # An existing variant sent without its options: they are its own.
            options = product.product_template_attribute_value_ids

        # Keep the exact figure the customer is looking at on the tablet.
        currency = request.website.currency_id if request.website else product.currency_id
        entry = {
            'product': product,
            'options': options,
            'price': float(price) if price else None,
            'currency': currency if price else None,
        }

        def key(prod, opts):
            return (prod.id, tuple(sorted(opts.ids)))

        entries = [entry]
        if mode == 'compare':
            # What is on the wall stays, the new piece joins at the end; the
            # same piece sent twice just moves to the end.
            kept = [
                {'product': slot.product_id, 'options': slot.option_ids,
                 'price': slot.price, 'currency': slot.currency_id}
                for slot in screen.slot_ids
                if key(slot.product_id, slot.option_ids) != key(product, options)
            ]
            entries = kept + [entry]
        result = screen.sudo()._push_entries(entries, mode=mode)
        screen = screen.with_context(lang=screen._lang())
        message = ''
        if result['dropped']:
            names = ', '.join(
                p.default_code or p.product_tmpl_id.default_code or p.product_tmpl_id.name
                for p in result['dropped'])
            message = screen.env._(
                "The wall holds %(max)s pieces: %(names)s was taken off to make room.",
                max=result['limit'], names=names)
        return {
            'ok': True,
            'screen': screen.name,
            'mode': mode,
            'count': result['count'],
            'limit': result['limit'],
            'message': message,
        }

    @http.route('/showroom/remove', type='jsonrpc', auth='user', website=True)
    def remove(self, slot_id=None, screen_id=None, **kw):
        """Take one piece off the wall and leave the others where they were."""
        if not _may_push(request.env.user):
            return {'error': _("You are not allowed to drive the showroom screen.")}
        screen, error = self._pick_screen(screen_id)
        if error:
            return {'error': error}
        screen.sudo()._remove_slot(int(slot_id or 0))
        return {'ok': True}

    @http.route('/showroom/screens', type='jsonrpc', auth='user', website=True)
    def screens(self, **kw):
        """Which screens this user may drive; drives the buttons in the shop."""
        if not _may_push(request.env.user):
            return {'screens': []}
        screens = request.env['xb.showroom.screen']._for_user(request.env.user)
        env = request.env
        return {
            'screens': [
                {'id': s.id, 'name': s.name, 'panels': s.panels,
                 'token': s.access_token, 'compare_max': s._compare_limit()}
                for s in screens
            ],
            'labels': {
                'on_air': env._("On the wall:"),
                'idle': env._("Showing the shop window"),
                'pushed': env._("On the wall."),
                'comparing': env._("On the wall: comparing %s."),
                'comparing_of': env._("Comparing %(count)s of %(max)s"),
                'cleared': env._("Back to the shop window."),
                'new_compare': env._("New comparison"),
                'compare_ready': env._("Ready: add the pieces to compare."),
                'back_idle': env._("Back to idle"),
                'remove': env._("Take off the wall"),
                'removed': env._("Taken off the wall."),
                'unknown': env._("Could not tell which piece to show."),
                'screen_set': env._("This tablet now sends to: %s"),
            },
        }

    @http.route('/showroom/clear', type='jsonrpc', auth='user', website=True)
    def clear(self, screen_id=None, **kw):
        if not _may_push(request.env.user):
            return {'error': _("You are not allowed to drive the showroom screen.")}
        screen, error = self._pick_screen(screen_id)
        if error:
            return {'error': error}
        screen.sudo().action_clear()
        return {'ok': True}

    def _pick_screen(self, screen_id=None):
        """``(screen, error)``: the screen this user asked for, if theirs.

        A tablet remembers its wall, but the id it sends is only a request:
        a screen of another company, or of a branch the user is not listed
        on, is refused rather than silently swapped for another one.
        """
        allowed = request.env['xb.showroom.screen']._for_user(request.env.user)
        if screen_id:
            screen = allowed.filtered(lambda s: s.id == int(screen_id))
            if not screen:
                return screen, _("You cannot send pieces to that screen.")
            return screen, None
        if not allowed:
            return allowed, _("No showroom screen is configured.")
        return allowed[:1], None
