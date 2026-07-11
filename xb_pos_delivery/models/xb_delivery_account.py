# -*- coding: utf-8 -*-
import json
import logging
import secrets
import uuid
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .. import const

_logger = logging.getLogger(__name__)


class XbDeliveryAccount(models.Model):
    _name = 'xb.delivery.account'
    _description = 'Food Delivery Platform Account'
    _inherit = ['pos.load.mixin']

    def _default_webhook_secret(self):
        return secrets.token_urlsafe(24)

    name = fields.Char(compute='_compute_name', store=True)
    provider = fields.Selection(const.PROVIDERS, required=True, default='uber_eats')
    config_id = fields.Many2one(
        'pos.config', string='Point of Sale', required=True, ondelete='cascade',
        help='POS (store) connected to the delivery platform.')
    company_id = fields.Many2one(related='config_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    active = fields.Boolean(default=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ], default='draft', copy=False)
    connection_msg = fields.Char(readonly=True, copy=False,
                                 help='Last connection diagnostic message.')

    # --- Credentials (generic names, per-provider meaning) ---
    client_id = fields.Char(
        string='Client ID / App ID', groups='point_of_sale.group_pos_manager',
        help='Uber Eats: application Client ID.\nDiDi Food: App ID.')
    client_secret = fields.Char(
        string='Client Secret / App Secret', groups='point_of_sale.group_pos_manager',
        help='Uber Eats: application Client Secret (also used to verify webhook '
             'signatures).\nDiDi Food: App Secret (used to sign every request).')
    external_store_id = fields.Char(
        string='Store ID on the Platform',
        help='Uber Eats: Store UUID.\nDiDi Food: Shop ID.')
    access_token = fields.Char(groups='point_of_sale.group_pos_manager', copy=False)
    token_expiry = fields.Datetime(copy=False)
    webhook_secret = fields.Char(
        default=_default_webhook_secret, required=True, copy=False,
        groups='point_of_sale.group_pos_manager',
        help='Random secret embedded in the webhook URL of this account.')
    webhook_url = fields.Char(compute='_compute_webhook_url')
    sandbox = fields.Boolean(
        string='Test / Sandbox Mode',
        help='Use the sandbox endpoints of the platform (when available).')

    # --- Behavior ---
    auto_accept = fields.Boolean(
        string='Auto-accept Orders',
        help='Accept every incoming order automatically. When disabled, the '
             'cashier confirms each order in the POS.')
    default_prep_time = fields.Integer(
        string='Default Preparation Time (min)', default=20)
    closed_session_policy = fields.Selection([
        ('reject', 'Reject the order on the platform'),
        ('ignore', 'Ignore (platform will time out)'),
    ], string='If the POS is Closed', default='reject', required=True,
        help='What to do when an order arrives while no POS session is open.')

    # --- Menu ---
    pos_categ_ids = fields.Many2many(
        'pos.category', string='Categories to Publish',
        help='POS categories exported to the platform menu. Leave empty to '
             'publish every product available in this POS.')
    pricelist_id = fields.Many2one(
        'product.pricelist', string='Platform Pricelist', check_company=True,
        help='Optional pricelist applied when building the platform menu, e.g. '
             'to compensate the platform commission. Prices are sent tax '
             'included.')
    fiscal_position_id = fields.Many2one(
        'account.fiscal.position', string='Fiscal Position', check_company=True,
        help='Optional fiscal position applied to incoming orders.')
    menu_last_sync = fields.Datetime(readonly=True, copy=False)
    menu_last_result = fields.Char(readonly=True, copy=False)

    # --- Accounting ---
    payment_method_id = fields.Many2one(
        'pos.payment.method', string='Payment Method', copy=False,
        help='POS payment method used to register the money collected by the '
             'platform. Created automatically with its own journal.')

    order_count = fields.Integer(compute='_compute_order_count')

    _config_provider_uniq = models.Constraint(
        'unique(config_id, provider)',
        "This Point of Sale is already connected to that platform.",
    )

    @api.depends('provider', 'config_id')
    def _compute_name(self):
        provider_names = dict(const.PROVIDERS)
        for account in self:
            account.name = '%s · %s' % (
                provider_names.get(account.provider, account.provider or '?'),
                account.config_id.name or '?',
            )

    def _compute_webhook_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for account in self:
            secret = account.sudo().webhook_secret
            account.webhook_url = (
                '%s/xb_delivery/%s/%s/webhook' % (base_url, account.id, secret)
                if account.id and secret else False
            )

    def _compute_order_count(self):
        counts = dict(self.env['pos.order']._read_group(
            [('xb_delivery_account_id', 'in', self.ids)],
            ['xb_delivery_account_id'], ['__count'],
        ))
        for account in self:
            account.order_count = counts.get(account, 0)

    @api.model
    def _load_pos_data_domain(self, data, config):
        return [('config_id', '=', config.id)]

    @api.model
    def _load_pos_data_fields(self, config):
        # Only non-sensitive fields ever reach the POS front-end.
        return ['id', 'provider', 'state', 'auto_accept', 'default_prep_time']

    # ------------------------------------------------------------------
    # Driver dispatch
    # ------------------------------------------------------------------

    def _get_driver(self):
        """Return the API driver instance for this account's provider."""
        self.ensure_one()
        from ..drivers import base_driver
        driver_cls = base_driver.get_driver_class(self.provider)
        if not driver_cls:
            raise UserError(_('No driver registered for provider %s.', self.provider))
        return driver_cls(self.sudo())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_test_connection(self):
        self.ensure_one()
        try:
            message = self._get_driver().test_connection()
            self.write({'state': 'connected', 'connection_msg': message or _('Connection OK')})
            msg_type = 'success'
            message = self.connection_msg
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            self.write({'state': 'error', 'connection_msg': str(exc)[:500]})
            msg_type = 'danger'
            message = str(exc)
        return self._notify_user(_('Connection Test'), message, msg_type)

    def action_sync_menu(self):
        self.ensure_one()
        self._check_ready()
        snapshot = self._build_menu_snapshot()
        if not snapshot['items']:
            raise UserError(_(
                'There is nothing to publish: no product is available in this '
                'POS for the selected categories.'))
        try:
            result = self._get_driver().push_menu(snapshot)
        except Exception as exc:  # noqa: BLE001
            self._log('out', 'menu_sync', payload=snapshot, success=False, message=str(exc))
            self.write({'menu_last_result': str(exc)[:500]})
            raise UserError(_('Menu synchronization failed:\n%s', exc)) from exc
        self.write({
            'menu_last_sync': fields.Datetime.now(),
            'menu_last_result': result or _('%s items published', len(snapshot['items'])),
        })
        self._log('out', 'menu_sync', payload={'items': len(snapshot['items'])},
                  success=True, message=self.menu_last_result)
        return self._notify_user(_('Menu Synchronization'), self.menu_last_result, 'success')

    def action_set_store_online(self):
        return self._set_store_status(True)

    def action_set_store_offline(self):
        return self._set_store_status(False)

    def action_view_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delivery Orders'),
            'res_model': 'pos.order',
            'view_mode': 'list,form',
            'domain': [('xb_delivery_account_id', '=', self.id)],
        }

    def action_view_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delivery Logs'),
            'res_model': 'xb.delivery.log',
            'view_mode': 'list,form',
            'domain': [('account_id', '=', self.id)],
            'context': {'default_account_id': self.id},
        }

    def action_regenerate_webhook_secret(self):
        for account in self:
            account.sudo().webhook_secret = self._default_webhook_secret()
        return True

    def _set_store_status(self, online):
        self.ensure_one()
        self._check_ready()
        try:
            self._get_driver().set_store_status(online)
        except Exception as exc:  # noqa: BLE001
            self._log('out', 'store_status', success=False, message=str(exc))
            raise UserError(_('Could not update the store status:\n%s', exc)) from exc
        self._log('out', 'store_status', success=True,
                  message='online' if online else 'offline')
        self.config_id._notify(const.BUS_STORE_EVENT, {
            'account_id': self.id, 'provider': self.provider, 'online': online,
        })
        return self._notify_user(
            _('Store Status'),
            _('%s is now %s.', self.name, _('online') if online else _('offline')),
            'success')

    def _check_ready(self):
        self.ensure_one()
        sudo_self = self.sudo()
        missing = []
        if not sudo_self.client_id:
            missing.append(_('Client ID / App ID'))
        if not sudo_self.client_secret:
            missing.append(_('Client Secret / App Secret'))
        if not sudo_self.external_store_id:
            missing.append(_('Store ID on the platform'))
        if missing:
            raise UserError(_('Missing credentials: %s', ', '.join(missing)))

    def _notify_user(self, title, message, msg_type):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': msg_type,
                       'sticky': False},
        }

    # ------------------------------------------------------------------
    # Menu snapshot (provider neutral)
    # ------------------------------------------------------------------

    def _menu_products(self):
        self.ensure_one()
        domain = [
            ('available_in_pos', '=', True),
            ('sale_ok', '=', True),
            ('company_id', 'in', [False, self.company_id.id]),
        ]
        if self.pos_categ_ids:
            domain.append(('pos_categ_ids', 'child_of', self.pos_categ_ids.ids))
        else:
            limited = self.config_id.limit_categories and self.config_id.iface_available_categ_ids
            if limited:
                domain.append(('pos_categ_ids', 'child_of',
                               self.config_id.iface_available_categ_ids.ids))
        special = self.env['product.product'].browse(
            self._special_product_ids()).mapped('product_tmpl_id')
        return self.env['product.template'].search(
            domain, order='sequence, name') - special

    def _menu_price(self, template):
        """Tax-included unit price sent to the platform."""
        self.ensure_one()
        product = template.product_variant_id
        if self.pricelist_id:
            price = self.pricelist_id._get_product_price(product, 1.0)
        else:
            price = product.lst_price
        taxes = template.taxes_id.filtered_domain(
            self.env['account.tax']._check_company_domain(self.company_id))
        if taxes:
            res = taxes.compute_all(
                price, self.currency_id, 1.0, product=product)
            price = res['total_included']
        return self.currency_id.round(price)

    def _build_menu_snapshot(self):
        """Provider-neutral menu structure; drivers convert it to API payloads.

        refs: category -> 'cat-<pos.category id>', item -> '<template id>',
        modifier group -> 'attr-<attribute line id>', option -> 'ptav-<id>'.
        """
        self.ensure_one()
        templates = self._menu_products()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        categories, cat_seen = [], set()
        items, groups, group_seen = [], [], set()
        item_statuses = {
            s.product_tmpl_id.id: s.is_available
            for s in self.env['xb.delivery.item.status'].search([
                ('account_id', '=', self.id)])
        }
        for template in templates:
            pos_categ = template.pos_categ_ids[:1]
            cat_ref = 'cat-%s' % pos_categ.id if pos_categ else 'cat-0'
            if cat_ref not in cat_seen:
                cat_seen.add(cat_ref)
                categories.append({
                    'ref': cat_ref,
                    'name': pos_categ.name or _('Menu'),
                    'sequence': pos_categ.sequence or 0,
                })
            group_refs = []
            for line in template.attribute_line_ids:
                group_ref = 'attr-%s' % line.id
                group_refs.append(group_ref)
                if group_ref in group_seen:
                    continue
                group_seen.add(group_ref)
                multi = line.attribute_id.display_type == 'multi'
                groups.append({
                    'ref': group_ref,
                    'name': line.attribute_id.name,
                    'min_permitted': 0 if multi else 1,
                    'max_permitted': len(line.product_template_value_ids) if multi else 1,
                    'options': [{
                        'ref': 'ptav-%s' % ptav.id,
                        'name': ptav.name,
                        'price': self.currency_id.round(
                            self._option_price_incl(template, ptav)),
                    } for ptav in line.product_template_value_ids if ptav.ptav_active],
                })
            image_url = False
            if template.image_1920:
                image_url = '%s/xb_delivery/img/%s/%s/%s' % (
                    base_url, self.id, self.sudo().webhook_secret, template.id)
            items.append({
                'ref': str(template.id),
                'name': template.name,
                'description': template.description_sale or '',
                'price': self._menu_price(template),
                'category_ref': cat_ref,
                'image_url': image_url,
                'available': item_statuses.get(template.id, True),
                'modifier_group_refs': group_refs,
            })
        categories.sort(key=lambda c: (c['sequence'], c['name']))
        return {
            'store': {
                'external_store_id': self.external_store_id,
                'name': self.config_id.name,
                'currency': self.currency_id.name,
            },
            'categories': categories,
            'items': items,
            'modifier_groups': groups,
        }

    def _option_price_incl(self, template, ptav):
        """Tax-included extra price of an attribute value."""
        extra = ptav.price_extra or 0.0
        if not extra:
            return 0.0
        taxes = template.taxes_id.filtered_domain(
            self.env['account.tax']._check_company_domain(self.company_id))
        if taxes:
            res = taxes.compute_all(
                extra, self.currency_id, 1.0, product=template.product_variant_id)
            extra = res['total_included']
        return extra

    # ------------------------------------------------------------------
    # Incoming orders (normalized dict -> pos.order)
    # ------------------------------------------------------------------

    def _special_product_ids(self):
        refs = [
            'xb_pos_delivery.product_delivery_fee',
            'xb_pos_delivery.product_packaging_fee',
            'xb_pos_delivery.product_platform_tip',
            'xb_pos_delivery.product_other_fee',
        ]
        ids = []
        for ref in refs:
            product = self.env.ref(ref, raise_if_not_found=False)
            if product:
                ids.append(product.id)
        return ids

    def _charge_product(self, charge_type):
        ref = {
            'delivery': 'xb_pos_delivery.product_delivery_fee',
            'packaging': 'xb_pos_delivery.product_packaging_fee',
            'tip': 'xb_pos_delivery.product_platform_tip',
        }.get(charge_type, 'xb_pos_delivery.product_other_fee')
        return self.env.ref(ref, raise_if_not_found=False)

    def _process_incoming_order(self, norm):
        """Create a draft pos.order from a normalized order dict.

        Returns the created order, or an existing one if the webhook was
        retried. Raises when no session is open (caller decides the policy).
        """
        self.ensure_one()
        PosOrder = self.env['pos.order'].sudo()
        existing = PosOrder.search([
            ('xb_delivery_account_id', '=', self.id),
            ('xb_delivery_identifier', '=', norm['external_id']),
        ], limit=1)
        if existing:
            _logger.info('xb_delivery: order %s already exists.', norm['external_id'])
            return existing
        session = self.config_id.current_session_id
        if not session or session.state != 'opened':
            raise UserError(_('No open POS session for %s.', self.config_id.name))

        partner = self._find_or_create_partner(norm.get('customer') or {})
        lines = []
        for item in norm['items']:
            lines.append(self._prepare_order_line(item))
        for charge in norm.get('charges') or []:
            line = self._prepare_charge_line(charge)
            if line:
                lines.append(line)

        pos_reference, tracking_number = self.config_id.sudo()._get_next_order_refs()
        notes = [norm.get('note') or '']
        for discount in norm.get('discounts') or []:
            # Platform-funded promos don't change what the restaurant is paid;
            # keep them as a note instead of altering the order total.
            if not discount.get('restaurant_funded'):
                notes.append(_('%(provider)s promotion: %(title)s',
                               provider=dict(const.PROVIDERS)[self.provider],
                               title=discount.get('title') or discount.get('code') or ''))
        order = PosOrder.create({
            'company_id': self.company_id.id,
            'config_id': self.config_id.id,
            'session_id': session.id,
            'partner_id': partner.id if partner else False,
            'pos_reference': pos_reference,
            'tracking_number': tracking_number,
            'fiscal_position_id': self.fiscal_position_id.id,
            'lines': lines,
            'amount_paid': 0.0,
            'amount_total': 0.0,
            'amount_tax': 0.0,
            'amount_return': 0.0,
            'user_id': session.user_id.id,
            'uuid': str(uuid.uuid4()),
            'xb_delivery_account_id': self.id,
            'xb_delivery_identifier': norm['external_id'],
            'xb_delivery_display_id': norm.get('display_id') or norm['external_id'],
            'xb_delivery_status': 'placed',
            'xb_delivery_type': norm.get('type') or 'delivery',
            'xb_prep_time': norm.get('prep_time') or self.default_prep_time,
            'xb_cash_due': norm.get('cash_due') or 0.0,
            'xb_delivery_json': json.dumps(norm.get('raw') or norm, default=str),
            'general_customer_note': '\n'.join(n for n in notes if n and n.strip()),
        })
        order._compute_prices()
        restaurant_discount = sum(
            d.get('amount', 0.0) for d in (norm.get('discounts') or [])
            if d.get('restaurant_funded'))
        if restaurant_discount:
            self._apply_restaurant_discount(order, restaurant_discount)
        self._log('in', 'order_placed', payload=norm.get('raw') or norm, success=True,
                  message=norm['external_id'])
        self._bus_order_event(order)
        if self.auto_accept:
            try:
                order.action_xb_accept()
            except Exception as exc:  # noqa: BLE001
                _logger.exception('xb_delivery: auto-accept failed for %s', order.id)
                self._log('out', 'auto_accept', success=False, message=str(exc))
        return order

    def _find_or_create_partner(self, customer):
        if not customer.get('name'):
            return self.env['res.partner']
        Partner = self.env['res.partner'].sudo()
        domain = [('name', '=', customer['name'])]
        if customer.get('phone'):
            domain.append(('phone', '=', customer['phone']))
        partner = Partner.search(domain, limit=1)
        vals = {
            'phone': customer.get('phone'),
            'email': customer.get('email'),
            'street': customer.get('street'),
            'city': customer.get('city'),
            'zip': customer.get('zip'),
        }
        vals = {k: v for k, v in vals.items() if v}
        if partner:
            if vals:
                partner.write(vals)
            return partner
        return Partner.create({'name': customer['name'], **vals,
                               'company_id': False, 'customer_rank': 1})

    def _prepare_order_line(self, item):
        """Build a pos.order.line command from a normalized item dict.

        item: {ref, name, qty, unit_price (tax incl, options included),
               options: [{ref, name, qty, price}], note}
        """
        from odoo.fields import Command
        product, ptavs = self._resolve_product(item)
        qty = item.get('qty') or 1
        price_unit = float(item.get('unit_price') or 0.0)
        taxes = product.taxes_id.filtered_domain(
            self.env['account.tax']._check_company_domain(self.company_id))
        if self.fiscal_position_id:
            taxes = self.fiscal_position_id.map_tax(taxes)
        price_unit = self._deflate_tax_included(price_unit, taxes, product)
        res = taxes.compute_all(
            price_unit, self.currency_id, qty, product=product) if taxes else {
            'total_excluded': price_unit * qty, 'total_included': price_unit * qty}
        note_parts = [item.get('note') or '']
        note_parts += [
            '%s x %s' % (opt.get('qty'), opt.get('name'))
            for opt in item.get('options') or [] if (opt.get('qty') or 1) > 1
        ]
        return Command.create({
            'product_id': product.id,
            'full_product_name': item.get('name') or product.display_name,
            'qty': qty,
            'price_unit': price_unit,
            'price_subtotal': res['total_excluded'],
            'price_subtotal_incl': res['total_included'],
            'tax_ids': [Command.set(taxes.ids)] if taxes else False,
            'attribute_value_ids': [Command.set(ptavs.ids)] if ptavs else False,
            'customer_note': '\n'.join(p for p in note_parts if p and p.strip()),
            'uuid': str(uuid.uuid4()),
        })

    def _deflate_tax_included(self, price, taxes, product):
        """Platform prices are always tax inclusive. When the product taxes
        are not price-included, remove the tax portion so compute_all lands
        exactly on the amount the platform charged."""
        if not taxes or not price:
            return price
        tax_types = taxes.flatten_taxes_hierarchy().mapped('price_include')
        if tax_types and all(tax_types):
            return price  # already price-included taxes: nothing to do
        AccountTax = self.env['account.tax'].sudo()
        base_line = AccountTax._prepare_base_line_for_taxes_computation(
            self.env['pos.order.line'],
            currency_id=self.currency_id,
            tax_ids=taxes,
            price_unit=price,
            quantity=1,
            special_mode='total_included',
            product_id=product,
        )
        AccountTax._add_tax_details_in_base_line(base_line, self.company_id)
        AccountTax._round_base_lines_tax_details([base_line], self.company_id)
        return base_line['tax_details']['total_excluded']

    def _resolve_product(self, item):
        """Map a normalized item back to (product.product, ptav recordset)."""
        Ptav = self.env['product.template.attribute.value'].sudo()
        template = None
        ref = str(item.get('ref') or '')
        if ref.isdigit():
            template = self.env['product.template'].sudo().browse(int(ref)).exists()
        if not template:
            template = self.env['product.template'].sudo().search(
                [('name', '=', item.get('name')),
                 ('available_in_pos', '=', True),
                 ('company_id', 'in', [False, self.company_id.id])], limit=1)
        if not template:
            raise UserError(_(
                'Product not found for delivery item %(name)s (ref %(ref)s). '
                'Re-synchronize the menu.', name=item.get('name'), ref=ref))
        ptav_ids = []
        for opt in item.get('options') or []:
            opt_ref = str(opt.get('ref') or '')
            if opt_ref.startswith('ptav-') and opt_ref[5:].isdigit():
                ptav = Ptav.browse(int(opt_ref[5:])).exists()
                if ptav and ptav.product_tmpl_id == template:
                    ptav_ids.append(ptav.id)
        ptavs = Ptav.browse(ptav_ids)
        # Variant resolution: use the variant matching the selected values,
        # else the first variant.
        product = template.product_variant_id
        variant_ptavs = ptavs.filtered(
            lambda p: p.attribute_id.create_variant != 'no_variant')
        if variant_ptavs:
            match = template.product_variant_ids.filtered(
                lambda v: variant_ptavs <= v.product_template_attribute_value_ids)
            product = match[:1] or product
        return product, ptavs

    def _prepare_charge_line(self, charge):
        """charge: {type: delivery|packaging|tip|other, name, amount (tax incl)}"""
        from odoo.fields import Command
        amount = float(charge.get('amount') or 0.0)
        if not amount:
            return False
        product = self._charge_product(charge.get('type'))
        if not product:
            _logger.warning('xb_delivery: charge product missing for %s', charge)
            return False
        taxes = product.taxes_id.filtered_domain(
            self.env['account.tax']._check_company_domain(self.company_id))
        if self.fiscal_position_id:
            taxes = self.fiscal_position_id.map_tax(taxes)
        amount = self._deflate_tax_included(amount, taxes, product)
        res = taxes.compute_all(
            amount, self.currency_id, 1.0, product=product) if taxes else {
            'total_excluded': amount, 'total_included': amount}
        return Command.create({
            'product_id': product.id,
            'full_product_name': charge.get('name') or product.name,
            'qty': 1,
            'price_unit': amount,
            'price_subtotal': res['total_excluded'],
            'price_subtotal_incl': res['total_included'],
            'tax_ids': [Command.set(taxes.ids)] if taxes else False,
            'uuid': str(uuid.uuid4()),
        })

    def _apply_restaurant_discount(self, order, amount):
        """Add a negative line for promos funded by the restaurant."""
        from odoo.fields import Command
        product = self.env.ref('xb_pos_delivery.product_other_fee',
                               raise_if_not_found=False)
        if not product or not amount:
            return
        order.sudo().write({'lines': [Command.create({
            'product_id': product.id,
            'full_product_name': _('Restaurant promotion'),
            'qty': 1,
            'price_unit': -amount,
            'price_subtotal': -amount,
            'price_subtotal_incl': -amount,
            'uuid': str(uuid.uuid4()),
        })]})
        order._compute_prices()

    # ------------------------------------------------------------------
    # Payments / status plumbing
    # ------------------------------------------------------------------

    def _ensure_payment_method(self):
        """Create (once) the journal + POS payment method of this account."""
        self.ensure_one()
        if self.payment_method_id:
            return self.payment_method_id
        provider_name = dict(const.PROVIDERS)[self.provider]
        code = '%s%s' % (const.JOURNAL_CODES.get(self.provider, 'XBD'), self.config_id.id)
        journal = self.env['account.journal'].sudo().search([
            ('code', '=', code), ('company_id', '=', self.company_id.id)], limit=1)
        if not journal:
            journal = self.env['account.journal'].sudo().create({
                'name': '%s - %s' % (provider_name, self.config_id.name),
                'code': code,
                'type': 'bank',
                'company_id': self.company_id.id,
            })
        method = self.env['pos.payment.method'].sudo().search([
            ('journal_id', '=', journal.id),
            ('xb_delivery_account_id', '=', self.id)], limit=1)
        if not method:
            method = self.env['pos.payment.method'].sudo().create({
                'name': '%s - %s' % (provider_name, self.config_id.name),
                'journal_id': journal.id,
                'company_id': self.company_id.id,
                'xb_delivery_account_id': self.id,
            })
        self.payment_method_id = method
        if method not in self.config_id.payment_method_ids:
            self.config_id.sudo().write({'payment_method_ids': [(4, method.id)]})
        return method

    def _register_order_payment(self, order):
        self.ensure_one()
        if order.state != 'draft':
            return
        method = self._ensure_payment_method()
        self.env['pos.make.payment'].sudo().with_context(
            active_ids=[order.id], active_id=order.id).create({
                'amount': order.amount_total,
                'payment_method_id': method.id,
            }).check()

    def _bus_order_event(self, order):
        self.config_id._notify(const.BUS_ORDER_EVENT, {
            'order_id': order.id,
            'status': order.xb_delivery_status,
            'account_id': self.id,
            'provider': self.provider,
        })

    def _log(self, direction, event, payload=None, success=True, message=False):
        self.env['xb.delivery.log'].sudo().create({
            'account_id': self.id,
            'direction': direction,
            'event': event,
            'payload': json.dumps(payload, default=str, indent=2) if payload else False,
            'success': success,
            'message': (message or '')[:1000],
        })

    @api.model_create_multi
    def create(self, vals_list):
        accounts = super().create(vals_list)
        for account in accounts:
            account._ensure_payment_method()
        return accounts

    @api.model
    def _cron_refresh_tokens(self):
        """Renew platform tokens before they expire (both platforms use
        ~30 day tokens)."""
        soon = fields.Datetime.now() + timedelta(days=5)
        accounts = self.search([('state', '=', 'connected')]).filtered(
            lambda a: not a.token_expiry or a.token_expiry < soon)
        for account in accounts:
            try:
                account._get_driver()._get_token(force=True)
                account._log('out', 'token_refresh', success=True)
            except Exception as exc:  # noqa: BLE001
                _logger.warning('xb_delivery: token refresh failed for %s: %s',
                                account.name, exc)
                account._log('out', 'token_refresh', success=False,
                             message=str(exc))
        return True
