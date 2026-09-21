# -*- coding: utf-8 -*-
"""Showroom screen: what the big screen is showing right now.

The tablet writes here (one record per physical screen) and the wall page
reads it. Nothing is pushed to the screen: the wall page polls, which keeps
this working behind any signage player without relying on its live-command
channel.
"""
import random
import secrets

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

# Physical screens standing side by side.
MAX_PANELS = 3
# Pieces a customer can hold up against each other. Beyond six nobody is
# comparing any more, and each piece would be too small to judge.
MAX_COMPARE = 6
# The shop window rotates in the browser; these bounds keep a mistyped
# setting from turning a public URL into a catalogue dump.
MAX_IDLE_PIECES = 48
MAX_IDLE_INTERVAL = 600
# How many published pieces a shuffled window draws from.
RANDOM_POOL = 300


class ShowroomScreen(models.Model):
    _name = 'xb.showroom.screen'
    _description = 'Showroom Screen'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda s: s.env.company)
    user_ids = fields.Many2many(
        'res.users', 'xb_showroom_screen_user_rel', 'screen_id', 'user_id',
        string='Sales people',
        domain="[('share', '=', False)]",
        help="Who may send pieces to this screen from a tablet. Leave it empty "
             "and every sales person of the company can. With one wall per "
             "branch, list each branch's staff so nobody lands a ring on the "
             "wall of another shop.")
    access_token = fields.Char(
        string='Access Token', required=True, copy=False, index=True,
        groups='sales_team.group_sale_manager',
        default=lambda s: secrets.token_urlsafe(24),
        help="Secret part of the wall URL. Anyone with the URL can watch the "
             "screen, so treat it like the screen itself: it is readable by "
             "sales managers only, and the tablet never needs to see it.")
    compare_max = fields.Integer(
        string='Pieces when comparing', default=6,
        help="How many pieces the wall can hold side by side. Two take a "
             "screen each with their differences listed in the middle; four "
             "to six share screens in halves. Sending one more drops the "
             "oldest, and the sales person is told.")
    panels = fields.Integer(
        string='Panels', default=3,
        help="How many physical screens sit side by side. On a multi-panel "
             "wall the piece is drawn on the centre panel so the bezels do "
             "not cut it.")
    show_price = fields.Selection(
        [('none', 'Do not show the price'),
         ('from', 'Show a "from" figure'),
         ('full', 'Show the full price')],
        string='Price on the wall', default='none', required=True,
        help="Shoppers are often accompanied, so showing the exact figure on "
             "a big screen is a commercial decision, not a technical one.")
    idle_mode = fields.Selection(
        [('own', 'Rotating shop window'),
         ('url', 'Another page'),
         ('plain', 'Plain branded screen')],
        string='When idle', default='own', required=True,
        help="A shop window built for this screen keeps the piece on the "
             "centre panel; pointing at another page is useful when you "
             "already have signage you like, but a page designed for one "
             "screen looks small and off-centre on a multi-panel wall.")
    idle_url = fields.Char(
        string='Idle page',
        help="Used when 'When idle' is set to another page. A relative path "
             "such as /shop works and avoids domain and login surprises.")
    idle_category_id = fields.Many2one(
        'product.public.category', string='Shop window category',
        help="Which products rotate when nobody is driving the screen. "
             "Empty means everything published.")
    idle_count = fields.Integer(
        string='Pieces in rotation', default=12)
    idle_interval = fields.Integer(
        string='Seconds per piece', default=9)
    idle_order = fields.Selection(
        [('price_desc', 'Most expensive first'),
         ('price_asc', 'Least expensive first'),
         ('sequence', 'Catalogue order'),
         ('random', 'Shuffled')],
        string='Rotation order', default='price_desc', required=True)
    idle_video = fields.Boolean(
        string='Video in the shop window', default=False,
        help="The shop window changes piece every few seconds, and a player "
             "that has to fetch and decode a new video that often stutters on "
             "the first seconds of each one. With this off the window rotates "
             "photographs, which is always smooth, and the video is kept for "
             "the moment a sales person puts a piece on the wall.")
    idle_qr_url = fields.Char(
        string='QR destination',
        help="Where the QR code on the idle screen points. Empty points at "
             "the shop.")
    idle_timeout = fields.Integer(
        string='Back to idle after (min)', default=4,
        help="0 keeps the last piece on screen until it is replaced.")
    poll_interval = fields.Integer(
        string='Refresh every (s)', default=2,
        help="How often the wall page asks Odoo what to show.")
    wall_style = fields.Selection(
        [('mosaic', 'Colour bands'), ('plain', 'Plain panels')],
        string='Wall style', default='mosaic', required=True,
        help="Colour bands turn each screen into a block — a deep gold panel "
             "for the piece in its case, clean paper for the piece itself and "
             "a full-bleed photo of it being worn. Plain panels keeps "
             "everything on one background.")
    title_mode = fields.Selection(
        [('product_name', 'The product name'),
         ('category', 'Category and metal')],
        string='Headline', default='product_name', required=True,
        help="Catalogues often name pieces by their internal reference, which "
             "reads badly on a two-metre screen. 'Category and metal' builds "
             "the headline from the data instead, until the commercial names "
             "are written.")
    video_fit = fields.Selection(
        [('cover', 'Fill the panel'),
         ('native', 'Its own size, never stretched')],
        string='Video on screen', default='cover', required=True,
        help="Catalogue videos are often smaller than the screen. Filling the "
             "panel stretches them, which shows on a wall and makes the player "
             "decode far more pixels than the file has — on a modest player "
             "that is what turns a smooth turn into a stutter. At its own size "
             "the piece looks sharp and plays light, but smaller.")
    theme = fields.Selection(
        [('light', 'Light'), ('dark', 'Dark')], default='light', required=True,
        string='Theme',
        help="Product shots on a white background read best on a light wall; "
             "pick dark for lifestyle or dark-background photography.")
    accent_color = fields.Char(
        string='Accent colour', default='#cda349',
        help="Used for the price, the rules and the brand line.")
    bg_color = fields.Char(string='Background colour', default='#0d0d0f')
    lang = fields.Selection(
        selection=lambda self: self.env['res.lang'].get_installed(),
        string='Language',
        help="Language the wall is written in. Defaults to the company's.")
    heading = fields.Char(
        string='Idle heading', translate=True,
        default=lambda s: s.env._("Ask us about this piece"))

    # --- live state (written by the tablet) --------------------------------
    mode = fields.Selection(
        [('single', 'One piece'), ('compare', 'Compare')],
        default='single', required=True, readonly=True)
    slot_ids = fields.One2many(
        'xb.showroom.slot', 'screen_id', string='On screen now', readonly=True)
    spotlight_at = fields.Datetime(string='Last push', readonly=True)
    wall_url = fields.Char(compute='_compute_wall_url')

    _access_token_uniq = models.Constraint(
        'unique(access_token)',
        "The wall access token must be unique.",
    )

    @api.constrains('panels', 'poll_interval', 'compare_max',
                    'idle_count', 'idle_interval', 'idle_url')
    def _check_panels(self):
        for screen in self:
            if not 1 <= (screen.idle_count or 12) <= MAX_IDLE_PIECES:
                raise ValidationError(
                    _("The shop window can rotate 1 to %s pieces.", MAX_IDLE_PIECES))
            if not 2 <= (screen.idle_interval or 9) <= MAX_IDLE_INTERVAL:
                raise ValidationError(
                    _("A piece can stay 2 to %s seconds on the shop window.", MAX_IDLE_INTERVAL))
            if screen.idle_url and not screen.idle_url.startswith(('/', 'http://', 'https://')):
                raise ValidationError(
                    _("The idle page must be a path like /my-page or a full https address."))
            if not 1 <= screen.panels <= MAX_PANELS:
                raise ValidationError(
                    _("A showroom screen can have 1 to %s panels.", MAX_PANELS))
            if not 2 <= screen.compare_max <= MAX_COMPARE:
                raise ValidationError(
                    _("The wall can compare 2 to %s pieces.", MAX_COMPARE))
            if screen.poll_interval < 1:
                raise ValidationError(_("The refresh interval must be at least 1 second."))

    @api.model
    def _for_user(self, user):
        """The screens ``user`` may drive from a tablet."""
        screens = self.sudo().search([('company_id', 'in', user.company_ids.ids)])
        return screens.filtered(lambda s: not s.user_ids or user in s.user_ids)

    def _compute_wall_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        for screen in self:
            screen.wall_url = '%s/showroom/wall/%s' % (
                base.rstrip('/'), screen.access_token or '')

    # ------------------------------------------------------------------
    # Live state
    # ------------------------------------------------------------------
    def _lang(self):
        self.ensure_one()
        return (self.lang
                or self.company_id.partner_id.lang
                or self.env.user.lang
                or 'en_US')

    def _idle_pieces(self, seed=None):
        """The pieces that rotate when nobody is driving the screen.

        Only published products with a picture: a shop window with a
        placeholder image is worse than a shorter rotation.

        ``seed`` keeps a shuffled window on the same pieces for a full round.
        Without it every poll would draw a different set and the wall would
        start over instead of rotating.
        """
        self.ensure_one()
        Template = self.env['product.template'].sudo()
        domain = [
            ('is_published', '=', True),
            ('image_1920', '!=', False),
            ('company_id', 'in', (False, self.company_id.id)),
        ]
        if self.idle_category_id:
            domain.append(('public_categ_ids', 'child_of', self.idle_category_id.id))
        order = {
            'price_desc': 'list_price desc',
            'price_asc': 'list_price asc',
            'sequence': 'website_sequence asc, id asc',
            'random': 'id asc',
        }.get(self.idle_order or 'price_desc')
        limit = min(max(self.idle_count or 12, 1), MAX_IDLE_PIECES)
        if self.idle_order == 'random':
            # Draw from a bounded pool: the wall asks often and the catalogue
            # can be tens of thousands of pieces long.
            pool = Template.search(domain, order='id asc', limit=RANDOM_POOL)
            chosen = random.Random(seed).sample(pool.ids, min(limit, len(pool)))
            return pool.browse(chosen).mapped('product_variant_id')
        return Template.search(domain, order=order, limit=limit).mapped('product_variant_id')

    def _is_live(self):
        """True while the pushed selection is still what the wall should show."""
        self.ensure_one()
        if not self.slot_ids or not self.spotlight_at:
            return False
        if not self.idle_timeout:
            return True
        age = fields.Datetime.now() - self.spotlight_at
        return age.total_seconds() < self.idle_timeout * 60

    def _compare_limit(self):
        """How many pieces this wall holds side by side."""
        self.ensure_one()
        return max(min(self.compare_max or MAX_COMPARE, MAX_COMPARE), 2)

    def _push(self, products, mode='single', prices=None):
        """Put ``products`` (product.product recordset) on this screen.

        ``prices`` is an optional {product_id: (amount, currency)} map so the
        wall shows exactly the figure the customer just saw on the tablet,
        instead of a price recomputed out of the website's context.
        """
        prices = prices or {}
        entries = []
        for product in products:
            amount, currency = prices.get(product.id, (None, None))
            entries.append({'product': product, 'price': amount, 'currency': currency})
        return self._push_entries(entries, mode=mode)

    def _push_entries(self, entries, mode='single'):
        """Put ``entries`` on this screen, oldest first.

        Each entry is ``{'product', 'options', 'price', 'currency'}``.
        ``options`` are the attribute values the customer picked on the
        tablet. With dynamic variants the exact combination often has no
        product yet, so the choice travels on the slot instead of forcing a
        variant into existence just to show it.
        """
        self.ensure_one()
        dropped = []
        if mode == 'compare':
            limit = self._compare_limit()
            if len(entries) > limit:
                dropped = entries[:len(entries) - limit]
                entries = entries[-limit:]
        else:
            limit = 1
            entries = entries[-1:]
        if not entries:
            raise UserError(_("Nothing to show on the wall."))
        vals = []
        for index, entry in enumerate(entries):
            product = entry['product']
            amount = entry.get('price')
            currency = entry.get('currency') or product.currency_id
            vals.append((0, 0, {
                'sequence': index,
                'product_id': product.id,
                'option_ids': [(6, 0, entry['options'].ids if entry.get('options') else [])],
                'price': amount if amount is not None else product.list_price,
                'currency_id': currency.id,
            }))
        self.write({
            'mode': mode,
            'spotlight_at': fields.Datetime.now(),
            'slot_ids': [(5, 0, 0)] + vals,
        })
        return {
            'count': len(entries),
            'dropped': [entry['product'] for entry in dropped],
            'limit': limit,
        }

    def _remove_slot(self, slot_id):
        """Take one piece off the wall; the rest stay where they were."""
        self.ensure_one()
        slot = self.slot_ids.filtered(lambda s: s.id == slot_id)
        if not slot:
            return False
        if len(self.slot_ids) <= 1:
            return self.action_clear()
        slot.unlink()
        # A fresh timestamp both restarts the idle countdown and tells the
        # wall that what it shows has changed.
        self.spotlight_at = fields.Datetime.now()
        return True

    def action_clear(self):
        """Send the wall back to its idle page."""
        self.write({'slot_ids': [(5, 0, 0)], 'spotlight_at': False})
        return True

    def action_open_wall(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': self.wall_url, 'target': 'new'}

    def action_reset_token(self):
        for screen in self:
            screen.access_token = secrets.token_urlsafe(24)
        return True


class ShowroomSlot(models.Model):
    _name = 'xb.showroom.slot'
    _description = 'Piece currently on a showroom screen'
    _order = 'sequence, id'

    screen_id = fields.Many2one(
        'xb.showroom.screen', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=0)
    product_id = fields.Many2one('product.product', required=True, ondelete='cascade')
    option_ids = fields.Many2many(
        'product.template.attribute.value', string='Chosen options',
        help="Metal, size... as picked on the tablet. Empty when the piece was "
             "sent from the catalogue grid, where no option was chosen yet.")
    price = fields.Float(digits='Product Price')
    currency_id = fields.Many2one('res.currency')
