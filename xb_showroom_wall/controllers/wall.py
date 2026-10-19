# -*- coding: utf-8 -*-
"""The wall page, its state feed, and the tablet's push endpoint.

The wall is a plain public URL that polls ``/state``: no live command has to
reach the signage player, so a player that only checks in every few minutes
still shows the piece instantly.
"""
import base64
import hashlib
import hmac
import html as html_escape
import io
import json
import re
import logging
import os
import shlex
import subprocess
import tempfile
import time

from odoo import http, _
from odoo.exceptions import AccessError
from odoo.http import request, Response
from odoo.tools import file_path, float_round

_logger = logging.getLogger(__name__)

# The wall asks for its state every couple of seconds, and building it reads
# attachments and samples the photo's backdrop with PIL. The answer only
# changes when the screen does, so it is built once and kept for a moment: a
# public URL must never cost a database round of work per poll.
_STATE_CACHE = {}
_STATE_CACHE_MAX = 64
# How long the wall shows «it's on your phone» after someone taps the
# counter's NFC stand.
TAP_SHOW = 12
LIVE_TTL = 30      # seconds; the key already changes with every push
IDLE_TTL = 60      # seconds; the rotation runs in the browser, not here


_ASSET_STAMP = None


# Files whose change must reload the wall page. A module that adds its own painter
# (see ``_wall_plugins``) appends its stylesheet and script here at import time.
STAMP_FILES = [
    'xb_showroom_wall/static/src/wall/wall.css',
    'xb_showroom_wall/static/src/wall/wall.js',
]


def _asset_stamp():
    """A number that changes whenever the wall's script or stylesheet does.

    Odoo serves module assets with a week of browser cache, and a signage
    player keeps them just as long: without this, a screen installed today
    would still be running last week's wall after an update, showing an
    older layout with no way to tell. The stamp rides on the URL, so a new
    file is a new URL and the player fetches it.
    """
    global _ASSET_STAMP
    if _ASSET_STAMP is None:
        stamp = 0
        for name in STAMP_FILES:
            try:
                stamp = max(stamp, int(os.path.getmtime(file_path(name))))
            except (OSError, FileNotFoundError, ValueError):
                pass
        _ASSET_STAMP = stamp or 1
    return _ASSET_STAMP


def _cached(key, ttl, build):
    now = time.time()
    hit = _STATE_CACHE.get(key)
    if hit and hit[0] > now:
        return hit[1]
    value = build()
    if len(_STATE_CACHE) > _STATE_CACHE_MAX:
        _STATE_CACHE.clear()
    _STATE_CACHE[key] = (now + ttl, value)
    return value

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


# Signage players embed a browser, and those browsers are often built
# without the patented H.264 decoder: an mp4 then plays everywhere except on
# the screen that matters, with no error to show for it. Every playable copy
# is offered and the player takes the first one it can decode.
_VIDEO_ORDER = ('video/webm', 'video/mp4')


def _video_sources(product):
    """The product's video in every format published on it, best first."""
    attachments = request.env['ir.attachment'].sudo().search([
        ('res_model', '=', 'product.template'),
        ('res_id', '=', product.product_tmpl_id.id),
        ('mimetype', 'in', _VIDEO_ORDER),
        ('public', '=', True),
    ], order='id desc')
    sources, seen = [], set()
    for mimetype in _VIDEO_ORDER:
        for attachment in attachments:
            if attachment.mimetype == mimetype and mimetype not in seen:
                seen.add(mimetype)
                sources.append({'url': '/web/content/%s' % attachment.id, 'type': mimetype})
    return sources


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
_SIDE_WORDS = ('lado', 'perfil', 'side', 'profile')


def _extra_shots(product, photo):
    """``{'case': url, 'hand': url}`` from the product's extra images."""
    images = product.product_tmpl_id.sudo().product_template_image_ids
    shots = {}
    leftovers = []
    for image in images.sorted(lambda i: (i.sequence, i.id)):
        label = (image.name or '').strip().lower()
        url = photo('i', image)
        if any(word in label for word in _CASE_WORDS):
            shots.setdefault('case', url)
        elif any(word in label for word in _HAND_WORDS):
            shots.setdefault('hand', url)
        elif any(word in label for word in _SIDE_WORDS):
            shots.setdefault('side', url)
        else:
            leftovers.append(url)
    # A photo that is not named as a case or hand shot is not passed off as
    # one: the wall would caption another angle "In its case". It stays an
    # extra angle of the piece instead.
    shots['angles'] = leftovers[:4]
    return shots


_CT = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:ct|qts|quilates?)\b', re.I)


def _carats(text):
    m = _CT.search(text or '')
    return float(m.group(1).replace(',', '.')) if m else 0.0


_MM = ((0.005, 1.0), (0.01, 1.3), (0.015, 1.5), (0.02, 1.7), (0.03, 2.0), (0.04, 2.2), (0.05, 2.4),
       (0.07, 2.7), (0.10, 3.0), (0.15, 3.4), (0.20, 3.8), (0.25, 4.1), (0.33, 4.4), (0.50, 5.2),
       (0.75, 5.9), (1.00, 6.5), (1.50, 7.4), (2.00, 8.2))


def _mm(carats):
    """Diameter in mm of a round brilliant of ``carats`` (jeweller's table)."""
    best = min(_MM, key=lambda row: abs(row[0] - carats))
    return ('%.1f' % best[1]).rstrip('0').rstrip('.')


def _stone_facts(env, tmpl, options=None):
    """Stones as a customer compares them, from the bill of materials:
    ``Stones`` (1 centre + N), ``Accents`` (N × size) and ``Total carats``.

    The bill lists one set of lines per kind of stone (zirconia, lab-grown,
    natural); the set that applies is the one of the stone picked on the
    tablet, or the zirconia every piece includes. Zirconia has no carats of
    its own, so accent sizes and the total come from the diamond lines of the
    same piece (same setting, same sizes), read as «diamond equivalent»."""
    if 'mrp.bom' not in env:
        return []
    bom = env['mrp.bom'].sudo().search(
        [('product_tmpl_id', '=', tmpl.id), ('product_id', '=', False)], limit=1)
    if not bom:
        return []
    stone_line = tmpl.attribute_line_ids.filtered(
        lambda l: (l.attribute_id.with_context(lang='en_US').name or '').lower() in ('stone', 'piedra'))
    picked = (options or env['product.template.attribute.value']).filtered(
        lambda v: v.attribute_line_id in stone_line)[:1]
    if not picked and stone_line:
        picked = stone_line.product_template_value_ids.filtered(
            lambda v: 'zirconia' in (v.name or '').lower())[:1]

    def applies(line, value):
        cond = line.bom_product_template_attribute_value_ids.filtered(
            lambda v: v.attribute_line_id in stone_line)
        return not cond or (value and value in cond)

    def split(value):
        centre, accents = 0.0, []
        split.centre_name = ''
        for line in bom.bom_line_ids:
            if not applies(line, value):
                continue
            name = line.product_id.display_name or ''
            is_centre = line.product_qty == 1 and ('central' in name.lower() or line.product_id.default_code)
            if is_centre:
                centre = _carats(name) or centre
                split.centre_name = line.product_id.name or ''
            else:
                accents.append((int(line.product_qty), _carats(name)))
        return centre, accents

    centre, accents = split(picked)
    centre_name = split.centre_name
    count = sum(q for q, _s in accents)
    kind = (picked.name or '') if picked else ''
    is_zirconia = 'zirconia' in kind.lower() or not kind
    if count and not any(size for _q, size in accents):
        # Zirconia: sizes from the lab-grown version of the same setting.
        lab = stone_line.product_template_value_ids.filtered(
            lambda v: 'laboratorio' in (v.name or '').lower() and _carats(v.name))[:1]
        _c, lab_accents = split(lab)
        if sum(q for q, _s in lab_accents) == count:
            accents = lab_accents
    facts = []
    # Centre stone: its kind and size, never hidden behind the accents.
    if is_zirconia:
        # «Zirconia central redonda» → «Zirconia redonda»: the shape is in the
        # bill of materials; the size is not recorded yet.
        central = re.sub(r'\s*central\b', '', centre_name, flags=re.I).strip() or env._("Cubic zirconia")
    else:
        central = re.sub(r'\s*·.*$', '', kind).replace('Diamante de laboratorio', 'Diamante laboratorio')
        central = re.sub(r'(\d+)\.00 ct', r'\1 ct', central)
    facts.append((env._("Centre stone"), central))
    if count:
        sizes = {}
        for q, size in accents:
            sizes[size] = sizes.get(size, 0) + q
        parts = []
        for size, q in sorted(sizes.items(), reverse=True):
            if not size:
                parts.append(str(q))
            elif is_zirconia:
                # Zirconia is not sold by the carat: the size goes in mm.
                parts.append('%s × %s mm' % (q, _mm(size)))
            else:
                parts.append('%s × %s ct' % (q, ('%.2f' % size).rstrip('0').rstrip('.')))
        facts.append((env._("Accents"), ' + '.join(parts)))
    if not is_zirconia:
        accent_ct = sum(q * size for q, size in accents)
        total = accent_ct + centre
        if total:
            value = '%.2f ct' % total
            if not centre:
                value = env._("%s + centre", value)
            facts.append((env._("Total carats"), value))
    return facts


def _piece_facts(env, product, chosen=False, options=None):
    """``(blurb, [(label, value)])``: a short description of the piece and the
    facts a customer weighs when comparing jewels — stones, weight and band
    width. They come from fields only a jewellery database has (Studio fields
    and the bill of materials), so each one is optional."""
    tmpl = product.product_tmpl_id.sudo()

    def text(field):
        if field not in tmpl._fields or not tmpl[field]:
            return ''
        return str(tmpl[field]).strip()

    facts = []
    facts += _stone_facts(env, tmpl, options)
    weight = 0.0
    if options and hasattr(tmpl, '_xb_proyectar_ptavs'):
        # The slot's product is whichever variant exists (dynamic variants),
        # often another metal: the weight is projected for the combination
        # the customer picked, or two versions of one ring weigh differently.
        try:
            comb = tmpl._get_first_possible_combination()
            for option in options.sudo():
                if option.product_tmpl_id == tmpl:
                    comb = (comb - comb.filtered(
                        lambda v: v.attribute_line_id == option.attribute_line_id)) | option
            weight = tmpl._xb_proyectar_ptavs(comb)[0] or 0.0
        except Exception as e:  # noqa: BLE001 - facts never break the wall
            _logger.warning("[SHOWROOM] weight projection failed for %s: %s", tmpl.id, e)
            weight = 0.0
    if not weight and chosen and 'xb_peso_proyectado' in product._fields:
        weight = product.sudo().xb_peso_proyectado or 0.0
    if not weight:
        try:
            weight = float(text('x_studio_peso_joya').replace(',', '.') or 0)
        except ValueError:
            weight = 0.0
    if weight:
        facts.append((env._("Weight"), env._("%s g approx.", ('%.1f' % weight))))
    width = text('x_studio_ancho_joya')
    if width:
        facts.append((env._("Band width"), env._("%s mm", width)))
    return text('x_studio_descripcion'), facts


_METAL_WORDS = ('metal', 'material')


def _is_metal(label):
    return (label or '').strip().lower() in _METAL_WORDS


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


# Catalogue photos are stored as PNG of well over a megabyte each, and Odoo
# serves them with ``no-cache``. A browser on a desk shrugs that off; a
# signage player painting three screens could not: every nine seconds it had
# to fetch and decode four megabytes again, and the change of piece caught it
# half way — one screen with its photo, the other two blank or half drawn.
# The wall gets its own copy instead: JPEG, a tenth of the weight, and cached
# for good, because the URL changes whenever the photo does.
_PHOTO_CACHE = {}
_PHOTO_CACHE_MAX = 160
_PHOTO_KINDS = {
    # kind: (model, field)
    'p': ('product.product', 'image_1920'),
    'r': ('product.product', 'image_1024'),
    'i': ('product.image', 'image_1024'),
}


def _photo_version(record):
    stamp = record.write_date
    if record._name == 'product.product':
        stamp = max(stamp, record.product_tmpl_id.write_date)
    return int(stamp.timestamp()) if stamp else 0


def _photo_bytes(raw):
    """The photo as a JPEG on white, or ``None`` when it cannot be read."""
    try:
        from PIL import Image
        image = Image.open(io.BytesIO(raw))
        image.load()
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGBA')
            flat = Image.new('RGB', image.size, (255, 255, 255))
            flat.paste(image, mask=image.getchannel('A'))
            image = flat
        else:
            image = image.convert('RGB')
        out = io.BytesIO()
        image.save(out, 'JPEG', quality=88, optimize=True)
        return out.getvalue()
    except Exception as e:  # pragma: no cover - the original is served instead
        _logger.warning("[SHOWROOM] could not convert a photo: %s", e)
        return None


def _may_show(screen, template):
    """A piece may go on the wall when the shop already shows it, or when
    someone ticked it for the wall.

    The wall is a public page. A published piece is public anyway; one that
    is not (a kiosk-only item, say) only reaches it because staff ticked
    «Show on the showroom wall» on it. One from another company has no
    business on this screen. Checking here is what keeps the push routes and
    the photo route from turning into a catalogue reader for whoever holds
    the wall's link.
    """
    if not template:
        return False
    if template.company_id.id not in (False, screen.company_id.id):
        return False
    return bool(template.is_published or template.xb_showroom_enabled)


def _tap_token(screen):
    """The short secret printed on the counter's NFC stand.

    Derived from the screen's own token, so the stand needs no field of its
    own, and the wall's token never leaves the player: a tag can be read by
    anyone who picks it up."""
    secret = screen.env['ir.config_parameter'].sudo().get_param('database.secret') or ''
    raw = hmac.new(secret.encode(), ('tap:%s' % screen.access_token).encode(),
                   hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw)[:12].decode()


def _tap_key(screen):
    return 'xb_showroom_wall.tap.%s' % screen.id


def _tap_read(screen):
    # Read straight from the table: the wall asks every second, and going
    # through the parameter cache would mean flushing every worker's cache on
    # each tap.
    screen.env.cr.execute(
        "SELECT value FROM ir_config_parameter WHERE key = %s", [_tap_key(screen)])
    row = screen.env.cr.fetchone()
    try:
        return float(row[0]) if row else 0.0
    except (TypeError, ValueError):
        return 0.0


def _tap_write(screen):
    screen.env.cr.execute("""
        INSERT INTO ir_config_parameter (key, value, create_date, write_date)
        VALUES (%s, %s, now() at time zone 'UTC', now() at time zone 'UTC')
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, write_date = EXCLUDED.write_date
    """, [_tap_key(screen), str(time.time())])


def _shop_url(base, slot):
    """The product page with the slot's combination already chosen: the shop
    selects whatever ``attribute_values`` lists (product.attribute.value ids)."""
    url = '%s%s' % (base, slot.product_id.product_tmpl_id.website_url or '/shop')
    if slot.option_ids:
        url += '?attribute_values=%s' % ','.join(
            str(i) for i in slot.option_ids.sudo().product_attribute_value_id.ids)
    return url


def _option_titles(slots):
    """What sets each slot apart when they are versions of one design:
    ``{slot.id: 'Diamante de laboratorio 1.00 ct'}``, empty when they are
    different designs or there is only one."""
    if len(slots) < 2:
        return {}
    names = {s.product_id.product_tmpl_id.name for s in slots}
    if len(names) != 1:
        return {}
    titles = {}
    for slot in slots:
        parts = []
        for option in slot.option_ids:
            if all(option.name in other.option_ids.mapped('name') for other in slots):
                continue
            label = option.name or ''
            if re.fullmatch(r'[\d.,]+', label.strip()):
                label = '%s %s' % (option.attribute_id.name, label)
            parts.append(label)
        titles[slot.id] = ' · '.join(parts)
    return titles


# The wall says the name of the piece just sent («Bellagio»). The voice is
# made on the server by whatever command `xb_showroom_wall.tts_command` holds
# (it reads the text on stdin and writes a WAV to {out}), once per name, and
# kept as an attachment. Without the parameter the wall stays silent.
VOICE_PREFIX = 'xb_showroom_voice_'
VOICE_SHOW = 30   # seconds after a push during which the wall may still say it


def _voice_text(product):
    """The name to say: the commercial name before its description
    («Bellagio · Solitario con doble pavé» → «Bellagio»)."""
    name = (product.product_tmpl_id.name or '').strip()
    for separator in _NAME_SEPARATORS:
        if separator in name:
            return name.split(separator)[0].strip()
    return name


def _voice_attachment(env, text):
    """The MP3 that says ``text``, made on first use; empty recordset when
    the voice is not configured or could not be made."""
    attachments = env['ir.attachment'].sudo()
    params = env['ir.config_parameter'].sudo()
    command = (params.get_param('xb_showroom_wall.tts_command') or '').strip()
    if not command or not text:
        return attachments.browse()
    chime = params.get_param('xb_showroom_wall.tts_chime', '1') not in ('0', 'False', 'false', '')
    key = hashlib.sha1(('%s|%s|%s' % (command, chime, text)).encode()).hexdigest()[:20]
    name = '%s%s.mp3' % (VOICE_PREFIX, key)
    found = attachments.search([('res_model', '=', 'xb.showroom.screen'), ('name', '=', name)], limit=1)
    if found:
        return found
    try:
        with tempfile.TemporaryDirectory() as tmp:
            wav, mp3 = os.path.join(tmp, 'voice.wav'), os.path.join(tmp, 'voice.mp3')
            subprocess.run(shlex.split(command.replace('{out}', wav)), input=text.encode(),
                           capture_output=True, timeout=30, check=True)
            if chime:
                # A soft two-note bell first: it turns heads before the name.
                graph = ('[0][1]amix=inputs=2,volume=0.35,afade=t=in:d=0.01,'
                         'afade=t=out:st=0.15:d=1.05,aresample=22050,aformat=channel_layouts=mono[c];'
                         'anullsrc=r=22050:cl=mono,atrim=0:0.3[s];'
                         '[2]aresample=22050,aformat=channel_layouts=mono[v];'
                         '[c][s][v]concat=n=3:v=0:a=1,loudnorm=I=-16:TP=-1.5')
                args = ['-f', 'lavfi', '-i', 'sine=frequency=1318:duration=1.2',
                        '-f', 'lavfi', '-i', 'sine=frequency=1976:duration=1.2',
                        '-i', wav, '-filter_complex', graph]
            else:
                args = ['-i', wav, '-af', 'loudnorm=I=-16:TP=-1.5']
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y'] + args + ['-ac', '1', '-b:a', '64k', mp3],
                           capture_output=True, timeout=30, check=True)
            with open(mp3, 'rb') as handle:
                data = handle.read()
    except Exception as e:  # noqa: BLE001 - the voice never blocks the wall
        _logger.warning("[SHOWROOM] voice for %r failed: %s", text, e)
        return attachments.browse()
    return attachments.create({
        'name': name, 'raw': data, 'mimetype': 'audio/mpeg',
        'res_model': 'xb.showroom.screen', 'res_id': 0,
    })


def _voice_key(screen):
    return 'xb_showroom_wall.voice.%s' % screen.id


def _price_label(screen, slot):
    if screen.show_price == 'none' or not slot.price:
        return ''
    currency = slot.currency_id or screen.company_id.currency_id
    amount = slot.price
    if screen.show_price == 'from' and not slot.option_ids:
        # The push already stored the shop's own «from» figure (cheapest gold
        # of the piece, as the tablet would show it), so it goes out as is.
        return screen.env._("From %s") % _money(amount, currency)
    return _money(amount, currency)


_KT = re.compile(r'(\d+)\s*k', re.I)


def _from_price(template):
    """The shop's «from» price of ``template``: the default combination with
    the metal swapped for each GOLD the piece offers, cheapest wins. Silver
    and steel are left out on purpose: «from» on a gold engagement ring must
    not quote the silver version. Needs a website request (pricelist, taxes).
    None when the piece has no metal choice or the shop cannot price it."""
    try:
        comb = template._get_first_possible_combination()
        line = template.valid_product_template_attribute_line_ids.filtered(
            lambda l: (l.attribute_id.with_context(lang='en_US').name or '').lower() == 'metal')
        if not line:
            return None
        golds = line.product_template_value_ids._only_active().filtered(
            lambda v: 'oro' in (v.name or '').lower() and 'imitaci' not in (v.name or '').lower()
            and _KT.search(v.name or ''))
        prices = []
        for value in golds:
            option = (comb - comb.filtered(lambda v: v.attribute_line_id == line)) | value
            info = template._get_combination_info(option)
            if info.get('price'):
                prices.append(info['price'])
        return min(prices) if prices else None
    except Exception as e:  # noqa: BLE001 - a price must never stop the push
        _logger.warning("[SHOWROOM] «from» price failed for %s: %s", template.id, e)
        return None


def _shop_pricelist(screen):
    """The pricelist the shop of the screen's company sells with."""
    env = screen.env['product.pricelist'].sudo()
    site = screen.env['website'].sudo().search([('company_id', '=', screen.company_id.id)], limit=1)
    return (site and env.search([('website_id', '=', site.id)], limit=1)) \
        or env.search([('company_id', '=', screen.company_id.id)], limit=1)


_COLOURS = ('blanco', 'amarillo', 'rosa', 'bitono', 'florentino')


def _karat_prices(screen, product, options=None):
    """``([{label, amount, chosen}], stone)``: the shop's price in 10K, 14K and
    18K, taxes as the shop shows them (included).

    Without ``options`` (sent from the grid) it is the piece's «from»: the
    default combination, cheapest gold of each karat. With the options the
    customer picked on the tablet, the stone, size and colour of gold are
    kept and only the karat changes, so the wall answers «how much is MY
    ring in 14K or 18K»; the karat they chose is flagged."""
    try:
        template = product.product_tmpl_id.sudo().with_company(screen.company_id)
        pricelist = _shop_pricelist(screen)
        if not pricelist:
            return [], ''
        lines = template.valid_product_template_attribute_line_ids
        line = lines.filtered(
            lambda l: (l.attribute_id.with_context(lang='en_US').name or '').lower() == 'metal')
        if not line:
            return [], ''
        comb = template._get_first_possible_combination()
        chosen_metal = None
        stone = ''
        for option in (options or template.env['product.template.attribute.value']).sudo():
            if option.product_tmpl_id != template:
                continue
            comb = (comb - comb.filtered(lambda v: v.attribute_line_id == option.attribute_line_id)) | option
            if option.attribute_line_id == line:
                chosen_metal = option
            elif (option.attribute_id.with_context(lang='en_US').name or '').lower() in ('stone', 'piedra'):
                stone = option.name or ''
        colour = None
        if chosen_metal:
            name = (chosen_metal.name or '').lower()
            colour = next((c for c in _COLOURS if c in name), None)
        best = {}
        for value in line.product_template_value_ids._only_active():
            name = (value.name or '').lower()
            match = _KT.search(value.name or '')
            if 'oro' not in name or 'imitaci' in name or not match:
                continue
            if colour and colour not in name:
                continue
            kt = int(match.group(1))
            option = (comb - comb.filtered(lambda v: v.attribute_line_id == line)) | value
            price = pricelist._get_product_price(
                template.with_context(**template._get_product_price_context(option)), 1.0)
            if template.taxes_id:
                price = template.taxes_id.compute_all(price, product=template)['total_included']
            if price and (kt not in best or price < best[kt][0]):
                best[kt] = (price, value == chosen_metal)
        rows = [{'label': '%sK' % kt, 'amount': best[kt][0], 'chosen': best[kt][1]}
                for kt in sorted(best) if kt in (10, 14, 18)]
        return rows, stone
    except Exception as e:  # noqa: BLE001 - prices never break the wall
        _logger.warning("[SHOWROOM] karat prices failed for %s: %s", product.id, e)
        return [], ''


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
    # Priced by weight and metal: its sale price is not on the product, and
    # the rotation has no shop context to work it out. Better no figure than
    # a wrong one.
    if getattr(product.product_tmpl_id, 'xb_precio_por_metal', False):
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
            'fit': screen.video_fit or 'cover',
            'panels': max(min(screen.panels, 3), 1),
            'poll': max(screen.poll_interval, 1),
            'accent': screen.accent_color or '#cda349',
            # Only pass a background when it is a deliberate override: the
            # theme in the stylesheet handles the usual light/dark case.
            'background': (screen.bg_color or '')
                          if screen.bg_color not in ('', False, DEFAULT_BG) else '',
            'stamp': _asset_stamp(),
        }
        logo = ''
        if screen.company_id.logo:
            logo = '/web/image/res.company/%s/logo' % screen.company_id.id
        # Everything below is written by staff, but the page is public: a
        # screen named with a stray tag would otherwise end up as markup.
        def safe(value):
            return html_escape.escape(str(value or ''), quote=True)
        plugins = self._wall_plugins(screen)

        html = """<!DOCTYPE html>
<html lang="%(lang)s"><head><meta charset="utf-8"/>
<title>%(title)s</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="robots" content="noindex, nofollow"/>
<script>
/* Safety net, kept apart from wall.js so it runs even when that never
   starts: if the wall has not painted a fresh state for a minute and the
   server answers, reload the page. A frozen shop player otherwise stays
   white until someone restarts it. */
(function () {
    var start = Date.now(), url = location.pathname, busy = false;
    window.__xbWallBeat = 0;
    setInterval(function () {
        if (busy || Date.now() - (window.__xbWallBeat || start) < 60000) { return; }
        busy = true;
        var control = window.AbortController ? new AbortController() : null;
        setTimeout(function () { if (control) { control.abort(); } busy = false; }, 10000);
        fetch(url + "/state", { cache: "no-store", credentials: "omit", signal: control ? control.signal : undefined })
            .then(function (response) { if (response.ok) { location.replace(url + "?r=" + Date.now()); } })
            .catch(function () { /* offline: try again on the next round */ });
    }, 15000);
})();
</script>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link rel="stylesheet" media="print" onload="this.media='all'" href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;1,400&amp;family=Jost:wght@300;400;500&amp;display=swap"/>
<link rel="stylesheet" href="/xb_showroom_wall/static/src/wall/wall.css?v=%(stamp)s"/>
%(plugin_css)s</head><body data-logo="%(logo)s" data-theme="%(theme)s" data-style="%(style)s" data-fit="%(fit)s">
<div id="wall" class="wall"></div>
<iframe id="idle" class="idle" referrerpolicy="no-referrer"></iframe>
<script id="cfg" type="application/json">%(config)s</script>
%(plugin_js)s<script src="/xb_showroom_wall/static/src/wall/wall.js?v=%(stamp)s" defer></script>
</body></html>""" % {
            'lang': safe((screen._lang() or 'es').split('_')[0]),
            'theme': safe(screen.theme or 'light'),
            'style': safe(screen.wall_style or 'mosaic'),
            'fit': safe(screen.video_fit or 'cover'),
            'title': safe(screen.name or 'Showroom'),
            'logo': safe(logo),
            'stamp': _asset_stamp(),
            # `</script>` inside a colour would close the block early.
            'config': json.dumps(config).replace('<', '\\u003c'),
            'plugin_css': ''.join('<link rel="stylesheet" href="%s?v=%s"/>\n' % (safe(p['css']), _asset_stamp())
                                  for p in plugins if p.get('css')),
            'plugin_js': ''.join('<script src="%s?v=%s" defer></script>\n' % (safe(p['js']), _asset_stamp())
                                 for p in plugins if p.get('js')),
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
        state = dict(self._state_dict(screen))
        screen.env.cr.execute(
            "SELECT value FROM ir_config_parameter WHERE key = %s", [_voice_key(screen)])
        row = screen.env.cr.fetchone()
        try:
            slot_id, voice_id, said = (row[0].split('|') if row else ('', '', '0'))
            if (screen._is_live() and time.time() - float(said) < VOICE_SHOW
                    and int(slot_id) in screen.slot_ids.ids):
                state['voice'] = {
                    'key': slot_id,
                    'url': '/showroom/wall/%s/voice/%s.mp3' % (token, int(voice_id)),
                }
        except (TypeError, ValueError):
            pass
        tapped = _tap_read(screen)
        if tapped and time.time() - tapped < TAP_SHOW:
            screen = screen.with_context(lang=screen._lang())
            state['tap'] = int(tapped)
            state['tap_text'] = screen.env._("Done! It's on your phone")
            state['tap_sub'] = screen.env._("Thank you for visiting us")
        return Response(json.dumps(state), headers=[
            ('Content-Type', 'application/json; charset=utf-8'),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
        ])

    def _wall_plugins(self, screen):
        """Extra stylesheets/scripts for the wall page: ``[{'css': url, 'js': url}]``.

        A module that knows how to draw its own kind of piece (e.g. wedding coins) adds its files here
        and registers a painter in ``window.XBWallPlugins``; the wall asks the painters first."""
        return []

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

        def photo(kind, record):
            return '/showroom/wall/%s/photo/%s/%s.jpg?v=%s' % (
                screen.access_token, kind, record.id, _photo_version(record))
        # A commercial name carries its own second line, so the metal moves
        # down to the data line instead of being dropped.
        name, description = _split_name(_headline(screen, product))
        blurb, facts = _piece_facts(screen.env, product, chosen=bool(options), options=options)
        specs = list(specs) + facts
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
            'blurb': blurb,
            # True when the second line is the description and the metal went
            # down to the data line: the comparison table must not ask for it
            # twice.
            'metal_in_specs': bool(description and metal),
            'product_name': product.product_tmpl_id.name,
            'variant': ', '.join(value for _label, value in ([('', metal)] if metal else []) + specs),
            'specs': [{'label': label, 'value': value} for label, value in specs],
            'reference': product.default_code or product.product_tmpl_id.default_code or '',
            'price': price,
            'image': photo('p', product),
            'ring': photo('r', product),
            'videos': _video_sources(product),
            'shots': _extra_shots(product, photo),
            'bg': _studio_background(product)
                  if (screen.theme == 'light' or screen.wall_style == 'mosaic') else '',
            # With a combination chosen the QR carries the slot, so the phone
            # opens the product page with that same metal, size and stone.
            'qr': qr if qr is not None else (
                '/showroom/wall/%s/qr/%s.png%s' % (
                    screen.access_token, product.id,
                    '?s=%s' % slot.id if slot and slot.option_ids else '')),
            'url': '%s%s' % (base.rstrip('/'), product.product_tmpl_id.website_url or ''),
        }

    def _state_dict(self, screen):
        """What the wall should show, cached for a few seconds.

        The key carries everything the answer depends on, so a push or a
        change of settings is seen at once and a quiet screen costs nothing.
        """
        if screen._is_live():
            key = ('live', screen.id, screen._lang(), str(screen.write_date),
                   str(screen.spotlight_at), tuple(screen.slot_ids.ids))
            ttl = LIVE_TTL
        else:
            # A shuffled shop window keeps the same pieces for a full round,
            # so the wall rotates instead of starting over on every poll.
            round_seconds = max((screen.idle_count or 12) * (screen.idle_interval or 9), 60)
            window = int(time.time() // round_seconds)
            key = ('idle', screen.id, screen._lang(), str(screen.write_date),
                   screen.idle_mode, window if screen.idle_order == 'random' else 0)
            ttl = IDLE_TTL
        return _cached(key, ttl, lambda: self._build_state(screen, key))

    def _build_state(self, screen, key=None):
        base = request.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        # A public request carries no language, so the wall would fall back to
        # English attribute names in front of the customer.
        screen = screen.with_context(lang=screen._lang())
        env = screen.env
        if not screen._is_live():
            state = {
                'stamp': _asset_stamp(),
                'live': False,
                'rev': 'idle-%s' % (screen.idle_mode or 'plain'),
                'idle_mode': screen.idle_mode or 'plain',
                'idle_video': screen.idle_video,
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
                    for product in screen._idle_pieces(seed=key[-1] if key else None)
                ]
                state['pieces'] = pieces
                # The QR caption doubles as the shop window's invitation.
                state['qr_text'] = screen.heading or env._(
                    "Scan to browse the collection")
                state['worn_text'] = env._("How it looks on")
                state['case_text'] = env._("In its case")
                state['ask_text'] = env._("Ask us about this piece")
                state['kicker_text'] = screen.company_id.name or ''
                state['rev'] = 'idle-own-%s' % ','.join(
                    str(piece['id']) for piece in pieces)
            return state
        pieces = [
            self._piece_dict(screen, slot.product_id, base,
                             price=_price_label(screen, slot),
                             options=slot.option_ids, slot=slot)
            for slot in screen.slot_ids
        ]
        if screen.mode == 'compare' and screen.show_price != 'none':
            for piece, slot in zip(pieces, screen.slot_ids):
                currency = slot.currency_id or screen.company_id.currency_id
                rows, stone = _karat_prices(screen, slot.product_id, slot.option_ids)
                piece['karats'] = [
                    {'label': row['label'], 'price': _money(row['amount'], currency),
                     'chosen': row['chosen']} for row in rows]
                # The stone type goes on the «Stones» row: what was picked on
                # the tablet, or the cubic zirconia every piece includes.
                piece['stone_type'] = stone or env._("Cubic zirconia")
                days = int(slot.product_id.product_tmpl_id.sale_delay or 0)
                piece['lead_text'] = (env._("%s days", days) if days != 1 else env._("1 day")) if days else ''
                piece['stone_note'] = ''
        return {
            'stamp': _asset_stamp(),
            'live': True,
            'qr_text': env._("Scan to take this piece with you"),
            'worn_text': env._("How it looks on"),
            'case_text': env._("In its case"),
            'ask_text': env._("Ask us about this piece"),
            'kicker_text': screen.company_id.name or '',
            'diff_text': env._("Compare and choose"),
            'diff_kicker': screen.compare_kicker or '',
            'diff_footer': screen.compare_footer or '',
            'lead_label': env._("Delivery"),
            'same_text': env._("Same design, you choose"),
            'size_text': env._("Size"),
            'natural_note': env._("+ natural centre diamond, quoted separately"),
            'quote_text': env._("Quoted separately"),
            'from_text': env._("From"),
            'qr_card_text': env._("Scan to see it on your phone"),
            'badge_texts': {
                'price': env._("Most accessible price"),
                'stones': env._("The most brilliant"),
                'gold': env._("The most gold"),
                'width': env._("Widest band"),
            },
            'price_text': env._("Price"),
            'metal_text': env._("Metal"),
            'rev': '%s-%s-%s' % (
                screen.mode, screen.spotlight_at, ','.join(str(p['slot']) for p in pieces)),
            'mode': screen.mode,
            'heading': screen.heading or '',
            'pieces': pieces,
        }

    @http.route('/showroom/wall/<string:token>/voice/<int:att_id>.mp3',
                type='http', auth='public', methods=['GET'], csrf=False,
                save_session=False, sitemap=False)
    def wall_voice(self, token, att_id, **kw):
        """The spoken name of a piece; only the wall's own voice files."""
        screen = _screen(token)
        voice = request.env['ir.attachment'].sudo().browse(att_id).exists()
        if (not screen or not voice or voice.res_model != 'xb.showroom.screen'
                or not (voice.name or '').startswith(VOICE_PREFIX)):
            return Response(status=404)
        return Response(voice.raw, headers=[
            ('Content-Type', 'audio/mpeg'),
            ('Cache-Control', 'public, max-age=31536000, immutable'),
        ])

    @http.route('/showroom/wall/<string:token>/photo/<string:kind>/<int:rec_id>.jpg',
                type='http', auth='public', methods=['GET'], csrf=False,
                save_session=False, sitemap=False)
    def wall_photo(self, token, kind, rec_id, **kw):
        """A catalogue photo, light enough for a signage player to keep up.

        Only photos of pieces this shop publishes are served, so the route is
        no wider than the product pages themselves.
        """
        screen = _screen(token)
        if not screen or kind not in _PHOTO_KINDS:
            return Response(status=404)
        model, field = _PHOTO_KINDS[kind]
        record = request.env[model].sudo().browse(rec_id).exists()
        template = record.product_tmpl_id
        if not template and model == 'product.image':
            template = record.product_variant_id.product_tmpl_id
        if not record or not _may_show(screen, template):
            return Response(status=404)
        key = (kind, record.id, _photo_version(record))
        body = _PHOTO_CACHE.get(key)
        if body is None:
            raw = record[field]
            if not raw:
                return Response(status=404)
            raw = base64.b64decode(raw)
            body = _photo_bytes(raw) or raw
            if len(_PHOTO_CACHE) >= _PHOTO_CACHE_MAX:
                _PHOTO_CACHE.clear()
            _PHOTO_CACHE[key] = body
        mimetype = 'image/jpeg' if body[:2] == b'\xff\xd8' else 'image/png'
        return Response(body, headers=[
            ('Content-Type', mimetype),
            # The version rides on the URL: a new photo is a new address.
            ('Cache-Control', 'public, max-age=31536000, immutable'),
        ])

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
        # Only what the wall is showing: the QR is for the customer standing in
        # front of it, not a way to walk the catalogue with the wall's link.
        on_screen = {piece['id'] for piece in self._state_dict(screen).get('pieces', [])}
        if not product or product.id not in on_screen:
            return Response(status=404)
        base = (request.env['ir.config_parameter'].sudo()
                .get_param('web.base.url') or '').rstrip('/')
        target = '%s%s' % (base, product.product_tmpl_id.website_url or '/shop')
        # The shop page selects the options listed in `attribute_values`
        # (ids of product.attribute.value), so the customer's phone shows the
        # same combination and price as the wall.
        slot = screen.slot_ids.filtered(lambda s: str(s.id) == str(kw.get('s') or ''))
        if slot and slot.product_id == product and slot.option_ids:
            target = _shop_url(base, slot)
        return _qr_response(target)

    # ------------------------------------------------------------------
    # The counter's NFC stand
    # ------------------------------------------------------------------
    @http.route('/showroom/t/<string:tap>', type='http', auth='public',
                methods=['GET'], csrf=False, save_session=False, sitemap=False)
    def wall_tap(self, tap, **kw):
        """A phone tapped the stand: show it what the wall is showing.

        The tag holds this one fixed address, so it never has to be written
        again; what it opens follows the wall. The wall itself answers with a
        short «it's on your phone», which is what makes the gesture visible."""
        screens = request.env['xb.showroom.screen'].sudo().search([('access_token', '!=', False)])
        screen = next((s for s in screens if hmac.compare_digest(_tap_token(s), tap or '')), None)
        if not screen:
            return Response(_("Unknown showroom screen."), status=404)
        _tap_write(screen)
        return Response(self._tap_page(screen.with_context(lang=screen._lang())), headers=[
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
        ])

    def _tap_page(self, screen):
        env = screen.env
        base = (env['ir.config_parameter'].sudo().get_param('web.base.url') or '').rstrip('/')
        company = screen.company_id
        shop = company.name or ''

        def esc(value):
            return html_escape.escape(str(value or ''), quote=True)

        live = screen._is_live()
        slots = screen.slot_ids if live else screen.slot_ids.browse()
        titles = _option_titles(slots)
        cards, lines = [], []
        for slot in slots:
            piece = self._piece_dict(screen, slot.product_id, base,
                                     price=_price_label(screen, slot),
                                     options=slot.option_ids, slot=slot)
            title = titles.get(slot.id) or piece['short'] or piece['product_name'] or piece['name']
            subtitle = piece['product_name'] if titles.get(slot.id) else piece['subtitle']
            url = _shop_url(base, slot)
            facts = [spec for spec in piece['specs']
                     if spec['label'].lower() not in ('piedra', 'stone')][:4]
            days = int(slot.product_id.product_tmpl_id.sale_delay or 0)
            if days:
                facts.append({'label': env._("Delivery"),
                              'value': env._("%s days", days) if days != 1 else env._("1 day")})
            cards.append("""<article class="card">
<a class="pic" href="%(url)s"><img src="%(img)s" alt="%(title)s" loading="lazy"/></a>
<div class="txt"><h2>%(title)s</h2><p class="sub">%(sub)s</p>
<p class="price">%(price)s</p><dl>%(facts)s</dl>
<a class="btn" href="%(url)s">%(see)s</a></div></article>""" % {
                'url': esc(url), 'img': esc(piece['image']), 'title': esc(title),
                'sub': esc(subtitle), 'price': esc(piece['price']),
                'facts': ''.join('<div><dt>%s</dt><dd>%s</dd></div>' % (esc(f['label']), esc(f['value']))
                                 for f in facts),
                'see': esc(env._("See it in the shop")),
            })
            lines.append('• %s%s%s\n%s' % (
                piece['product_name'] or title,
                (' · %s' % titles[slot.id]) if titles.get(slot.id) else '',
                (' · %s' % piece['price']) if piece['price'] else '', url))

        number = re.sub(r'\D', '', env['ir.config_parameter'].sudo().get_param(
            'xb_showroom_wall.whatsapp') or getattr(company, 'mobile', '') or company.phone or '')
        actions = ''
        if cards and number:
            from urllib.parse import quote
            text = env._("Hi! I'd like these pieces I saw at %s:", shop) + '\n\n' + '\n\n'.join(lines)
            actions += '<a class="btn wa" href="https://wa.me/%s?text=%s">%s</a>' % (
                number, quote(text), esc(env._("Send it to me on WhatsApp")))
        actions += '<a class="btn ghost" href="%s/appointment">%s</a>' % (
            esc(base), esc(env._("Book an appointment")))
        if not cards:
            body = '<section class="empty"><p>%s</p><a class="btn" href="%s">%s</a></section>' % (
                esc(env._("Right now the wall is showing our shop window.")),
                esc(screen.idle_qr_url or '%s/shop' % base), esc(env._("See the collection")))
        else:
            body = ''.join(cards)
        logo = ('<img class="logo" src="/web/image/res.company/%s/logo" alt="%s"/>' % (company.id, esc(shop))
                if company.logo else '<div class="logo-text">%s</div>' % esc(shop))
        return """<!DOCTYPE html><html lang="%(lang)s"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/><meta name="robots" content="noindex, nofollow"/>
<title>%(title)s · %(shop)s</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital@0;1&amp;family=Jost:wght@300;400;500&amp;display=swap"/>
<style>
:root{--bg:#FAF8F4;--ink:#14110E;--muted:#6f6556;--gold:#A6824C;--line:#e7dfd2;--card:#fff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:300 16px/1.5 Jost,system-ui,sans-serif}
header{padding:28px 20px 8px;text-align:center}.logo{height:40px;max-width:60%%}.logo-text{font:400 22px "Playfair Display",serif;letter-spacing:.2em}
h1{font:400 30px/1.15 "Playfair Display",Georgia,serif;margin:18px 0 4px}.lead{color:var(--muted);margin:0}
main{padding:12px 16px 140px;display:grid;gap:16px;max-width:560px;margin:0 auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.pic{display:block;background:#fff}.pic img{display:block;width:100%%;aspect-ratio:4/3;object-fit:contain;padding:8px}
.txt{padding:16px 18px 18px}h2{font:400 21px/1.2 "Playfair Display",serif;margin:0}.sub{color:var(--muted);margin:2px 0 0;font-size:14px}
.price{font-size:24px;font-weight:500;color:var(--gold);margin:10px 0 6px}
dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 14px;margin:8px 0 14px}dt{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}dd{margin:0;font-weight:400}
.btn{display:block;text-align:center;padding:13px 16px;border-radius:999px;background:var(--ink);color:#fff;text-decoration:none;font-weight:400;letter-spacing:.04em}
.btn.wa{background:#1f6f4a}.btn.ghost{background:transparent;color:var(--ink);border:1px solid var(--ink)}
.bar{position:fixed;left:0;right:0;bottom:0;padding:12px 16px calc(12px + env(safe-area-inset-bottom,0px));background:rgba(250,248,244,.96);border-top:1px solid var(--line);display:grid;gap:8px}
.bar .btn{max-width:528px;width:100%%;margin:0 auto}.empty{text-align:center;padding:24px 8px}.empty p{color:var(--muted)}
</style></head><body>
<header>%(logo)s<h1>%(title)s</h1><p class="lead">%(lead)s</p></header>
<main>%(body)s</main><nav class="bar">%(actions)s</nav></body></html>""" % {
            'lang': esc((screen._lang() or 'es').split('_')[0]), 'shop': esc(shop), 'logo': logo,
            'title': esc(env._("Your selection")),
            'lead': esc(env._("What you saw on the wall at %s", shop)),
            'body': body, 'actions': actions,
        }

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
        if mode not in ('single', 'compare'):
            return {'error': _("Unknown way of showing the piece.")}
        env = request.env
        # Read as the sales person, never as superuser: what they may not see
        # in the shop must not reach the wall either.
        try:
            template = env['product.template'].browse(int(template_id or 0)).exists()
            product = env['product.product'].browse(int(product_id or 0)).exists()
            options = env['product.template.attribute.value'].browse(
                [int(value) for value in (combination or []) if value]).exists()
            amount = float(price) if price else None
            template.check_access('read')
            product.check_access('read')
            options.check_access('read')
        except (TypeError, ValueError):
            return {'error': _("Could not tell which piece to show.")}
        except AccessError:
            return {'error': _("You cannot show that piece on the wall.")}
        if product:
            template = product.product_tmpl_id
        options = options.filtered(lambda v: v.product_tmpl_id == template)
        if not product and template:
            product = (template._get_variant_for_combination(options) if options else None) \
                or template.product_variant_id
        if not product:
            return {'error': _("That piece no longer exists.")}
        if not _may_show(screen, product.product_tmpl_id):
            return {'error': _(
                "Only pieces published in the shop of this company can go on the wall.")}
        if not product.product_tmpl_id.xb_showroom_enabled:
            return {'error': _(
                "This piece is not enabled for the wall. Tick «Show on the showroom wall» on the product.")}
        if not options and product_id:
            # An existing variant sent without its options: they are its own.
            options = product.product_template_attribute_value_ids

        # Keep the exact figure the customer is looking at on the tablet; a
        # screen that shows «from» stores the shop's own «from» figure.
        if screen.show_price == 'from' and not options:
            amount = _from_price(product.product_tmpl_id) or amount
        currency = request.website.currency_id if request.website else product.currency_id
        entry = {
            'product': product.sudo(),
            'options': options.sudo(),
            'price': amount,
            'currency': currency if amount is not None else None,
        }

        entries = [entry]
        repeated = False
        if mode == 'compare':
            # What is on the wall stays and the new piece joins at the end.
            # The same ring sent again moves to the end instead of showing up
            # twice. Two versions of one design are a real question («this
            # one with a lab diamond or a natural one?»), so the same model
            # joins when both carry a combination and the combinations differ;
            # sent from the grid (no combination) it still replaces itself.
            # Only the sales person's own pieces are compared: one a customer
            # sent from the kiosk gave way to this push, the latest wins.
            own = screen.slot_ids.filtered(lambda s: s.source == 'web')
            already = own.filtered(
                lambda s: s.product_id.product_tmpl_id == template and (
                    not options or not s.option_ids
                    or set(s.option_ids.ids) == set(options.ids)))
            repeated = bool(already)
            kept = [
                {'product': slot.product_id, 'options': slot.option_ids,
                 'price': slot.price, 'currency': slot.currency_id}
                for slot in own - already
            ]
            entries = kept + [entry]
        result = screen.sudo()._push_entries(entries, mode=mode)
        screen = screen.with_context(lang=screen._lang())
        message = ''
        if repeated:
            message = screen.env._("That piece was already on the wall; it moved to the end.")
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
        try:
            removed = screen.sudo()._remove_slot(int(slot_id or 0))
        except (TypeError, ValueError):
            removed = False
        # The wall may have changed under the tablet (another tablet, a sale):
        # saying "taken off" when nothing was is worse than saying nothing.
        return {'ok': bool(removed)}

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
                'moved_on': env._("That piece was no longer on the wall."),
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
