# -*- coding: utf-8 -*-
"""Uber Eats Marketplace API driver.

Docs: https://developer.uber.com/docs/eats
Auth: OAuth2 client_credentials (30-day tokens, cached on the account).
Money: integer minor units (centavos).
Webhook signature: X-Uber-Signature = HMAC-SHA256(raw body, client_secret).
"""
import hashlib
import hmac
import json
import logging
from datetime import timedelta

from odoo import fields, _
from odoo.tools import consteq

from .base_driver import BaseDeliveryDriver, DeliveryDriverError, register_driver

_logger = logging.getLogger(__name__)

PROD_API = 'https://api.uber.com'
PROD_AUTH = 'https://auth.uber.com/oauth/v2/token'
SANDBOX_API = 'https://test-api.uber.com'
SANDBOX_AUTH = 'https://sandbox-login.uber.com/oauth/v2/token'

SCOPES = 'eats.store eats.order eats.store.status.write'

# Uber requires accept/deny within ~11.5 minutes of the webhook.
DENY_CODE_DEFAULT = 'OTHER'
DENY_CODE_CLOSED = 'STORE_CLOSED'


@register_driver('uber_eats')
class UberEatsDriver(BaseDeliveryDriver):

    @property
    def api_base(self):
        return SANDBOX_API if self.account.sandbox else PROD_API

    @property
    def auth_url(self):
        return SANDBOX_AUTH if self.account.sandbox else PROD_AUTH

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _get_token(self, force=False):
        account = self.account
        if (not force and account.access_token and account.token_expiry
                and account.token_expiry > fields.Datetime.now() + timedelta(hours=12)):
            return account.access_token
        response = self._request('POST', self.auth_url, data={
            'client_id': account.client_id,
            'client_secret': account.client_secret,
            'grant_type': 'client_credentials',
            'scope': SCOPES,
        })
        if not response.ok:
            raise DeliveryDriverError(
                'Uber Eats authentication failed (%s): %s'
                % (response.status_code, response.text[:300]))
        data = response.json()
        token = data.get('access_token')
        if not token:
            raise DeliveryDriverError('Uber Eats did not return a token.')
        account.write({
            'access_token': token,
            'token_expiry': fields.Datetime.now() + timedelta(
                seconds=int(data.get('expires_in', 2592000))),
        })
        return token

    def _headers(self):
        return {
            'Authorization': 'Bearer %s' % self._get_token(),
            'Content-Type': 'application/json',
        }

    def _api(self, method, path, log_event=None, **kwargs):
        response = self._request(
            method, self.api_base + path, log_event=log_event,
            headers=self._headers(), **kwargs)
        if response.status_code == 401:
            # Token revoked (e.g. evicted by the 100-token cap): retry once.
            self._get_token(force=True)
            response = self._request(
                method, self.api_base + path, log_event=log_event,
                headers=self._headers(), **kwargs)
        if not response.ok:
            raise DeliveryDriverError(
                'Uber Eats API error %s on %s: %s'
                % (response.status_code, path, response.text[:300]))
        try:
            return response.json() if response.text else {}
        except ValueError:
            return {}

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    def test_connection(self):
        store = self._api('GET', '/v1/eats/stores/%s' % self.account.external_store_id)
        name = (store.get('store') or store).get('name') or self.account.external_store_id
        return _('Connected to Uber Eats store "%s".', name)

    def push_menu(self, snapshot):
        payload = self._build_menu_payload(snapshot)
        self._api('PUT', '/v2/eats/stores/%s/menus' % self.account.external_store_id,
                  log_event='uber_menu_put', data=json.dumps(payload))
        return _('%s items published to Uber Eats.', len(snapshot['items']))

    def set_store_status(self, online):
        self._api('POST', '/v1/eats/store/%s/status' % self.account.external_store_id,
                  data=json.dumps({
                      'status': 'ONLINE' if online else 'PAUSED',
                      'reason': 'POS' if online else 'Paused from POS',
                  }))
        return True

    def set_item_availability(self, template, available):
        item_id = str(template.id)
        suspension_info = {}
        if not available:
            suspension_info = {'suspension': {
                'suspend_until': 2147483647,  # indefinitely, until re-enabled
                'reason': 'Sold out (POS)',
            }}
        self._api('POST', '/v2/eats/stores/%s/menus/items/%s'
                  % (self.account.external_store_id, item_id),
                  data=json.dumps({'suspension_info': suspension_info}))
        return True

    def accept_order(self, order):
        self._api('POST', '/v1/eats/orders/%s/accept_pos_order'
                  % order.xb_delivery_identifier,
                  data=json.dumps({
                      'reason': 'Accepted by Odoo POS',
                      'external_reference_id': order.pos_reference or '',
                  }))
        return True

    def deny_order(self, order, reason):
        code = DENY_CODE_CLOSED if 'closed' in (reason or '').lower() else DENY_CODE_DEFAULT
        self._api('POST', '/v1/eats/orders/%s/deny_pos_order'
                  % order.xb_delivery_identifier,
                  data=json.dumps({
                      'reason': {'explanation': reason or 'Rejected', 'code': code},
                  }))
        return True

    def cancel_order(self, order, reason=None):
        self._api('POST', '/v1/eats/orders/%s/cancel' % order.xb_delivery_identifier,
                  data=json.dumps({'reason': 'OTHER', 'details': reason or ''}))
        return True

    def mark_ready(self, order):
        # Marketplace (Uber courier) orders have no "food ready" endpoint:
        # readiness is estimated from the prep time given at acceptance.
        return True

    def get_order(self, order_id):
        return self._api('GET', '/v2/eats/order/%s' % order_id)

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------

    def verify_webhook(self, headers, raw_body):
        signature = headers.get('X-Uber-Signature') or ''
        secret = (self.account.client_secret or '').encode()
        expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
        return bool(signature) and consteq(expected, signature.lower())

    # ------------------------------------------------------------------
    # Payload conversions
    # ------------------------------------------------------------------

    def _tax_rate(self, snapshot_item=None):
        """IVA rate of the account company's default POS taxes (MX: 16)."""
        taxes = self.env['account.tax'].sudo().search([
            ('company_id', '=', self.account.company_id.id),
            ('type_tax_use', '=', 'sale'),
            ('amount_type', '=', 'percent'),
        ], limit=1)
        return taxes.amount if taxes else 0

    @staticmethod
    def _cents(amount):
        return int(round((amount or 0.0) * 100))

    @staticmethod
    def _title(text):
        return {'translations': {'en_us': text or ' '}}

    def _build_menu_payload(self, snapshot):
        all_days = [{
            'day_of_week': day,
            'time_periods': [{'start_time': '00:00', 'end_time': '23:59'}],
        } for day in ('monday', 'tuesday', 'wednesday', 'thursday', 'friday',
                      'saturday', 'sunday')]
        categories = []
        for cat in snapshot['categories']:
            entities = [{'type': 'ITEM', 'id': item['ref']}
                        for item in snapshot['items']
                        if item['category_ref'] == cat['ref']]
            if entities:
                categories.append({
                    'id': cat['ref'],
                    'title': self._title(cat['name']),
                    'entities': entities,
                })
        items = []
        for item in snapshot['items']:
            entry = {
                'id': item['ref'],
                'external_data': 'odoo-tmpl-%s' % item['ref'],
                'title': self._title(item['name']),
                'description': self._title(item['description'] or item['name']),
                'price_info': {'price': self._cents(item['price'])},
                'tax_info': {'tax_rate': self._tax_rate()},
                'modifier_group_ids': {'ids': item['modifier_group_refs']},
                'suspension_info': {} if item['available'] else {
                    'suspension': {'suspend_until': 2147483647,
                                   'reason': 'Sold out'}},
            }
            if item.get('image_url'):
                entry['image_url'] = item['image_url']
            items.append(entry)
        modifier_groups = []
        for group in snapshot['modifier_groups']:
            modifier_groups.append({
                'id': group['ref'],
                'title': self._title(group['name']),
                'quantity_info': {'quantity': {
                    'min_permitted': group['min_permitted'],
                    'max_permitted': group['max_permitted'],
                }},
                'modifier_options': [{'type': 'ITEM', 'id': opt['ref']}
                                     for opt in group['options']],
            })
            # Modifier options are items themselves on Uber Eats.
            for opt in group['options']:
                items.append({
                    'id': opt['ref'],
                    'external_data': 'odoo-%s' % opt['ref'],
                    'title': self._title(opt['name']),
                    'price_info': {'price': self._cents(opt['price'])},
                    'tax_info': {'tax_rate': self._tax_rate()},
                })
        return {
            'menus': [{
                'id': 'menu-odoo',
                'title': self._title(_('Menu')),
                'service_availability': all_days,
                'category_ids': [cat['id'] for cat in categories],
            }],
            'categories': categories,
            'items': items,
            'modifier_groups': modifier_groups,
            'display_options': {},
        }

    def parse_order(self, payload):
        """Normalize a GET /v2/eats/order response."""
        order = payload.get('order') or payload
        cart = order.get('cart') or {}
        charges = order.get('charges') or {}
        eater = order.get('eater') or {}
        items = []
        for line in cart.get('items') or []:
            options = []
            extra_per_unit = 0.0
            for group in line.get('selected_modifier_groups') or []:
                for opt in group.get('selected_items') or []:
                    opt_qty = (opt.get('quantity') or {}).get('amount', 1) \
                        if isinstance(opt.get('quantity'), dict) else opt.get('quantity') or 1
                    opt_price = self._money(opt.get('price'), 'unit_price')
                    options.append({
                        'ref': str(opt.get('id') or ''),
                        'name': opt.get('title') or '',
                        'qty': opt_qty,
                        'price': opt_price,
                    })
                    extra_per_unit += opt_price * opt_qty
            qty = (line.get('quantity') or {}).get('amount', 1) \
                if isinstance(line.get('quantity'), dict) else line.get('quantity') or 1
            unit_price = self._money(line.get('price'), 'unit_price') + extra_per_unit
            items.append({
                'ref': str(line.get('id') or ''),
                'name': line.get('title') or '',
                'qty': qty,
                'unit_price': unit_price,
                'options': options,
                'note': line.get('special_instructions') or '',
            })
        cash_due = (charges.get('cash_amount_due') or {}).get('amount', 0) \
            if isinstance(charges.get('cash_amount_due'), dict) \
            else charges.get('cash_amount_due') or 0
        fulfillment = (order.get('type') or '').upper()
        order_type = 'pickup' if fulfillment in ('PICK_UP', 'DINE_IN') else 'delivery'
        discounts = []
        for promo in (charges.get('promotions') or {}).get('promotions', []) \
                if isinstance(charges.get('promotions'), dict) else []:
            discounts.append({
                'title': promo.get('name') or 'Promotion',
                'code': promo.get('external_promotion_id') or '',
                'amount': self._money(promo, 'discount_amount_applied'),
                'restaurant_funded': (promo.get('discount_provider') or '').upper()
                                     not in ('UBER', 'PLATFORM'),
            })
        return {
            'external_id': order.get('id'),
            'display_id': order.get('display_id') or order.get('id'),
            'type': order_type,
            'note': (cart.get('special_instructions') or ''),
            'prep_time': None,
            'cash_due': (cash_due or 0) / 100.0,
            'customer': {
                'name': ' '.join(filter(None, [
                    eater.get('first_name'), eater.get('last_name')])) or 'Uber Eats',
                'phone': eater.get('phone') or '',
            },
            'items': items,
            'charges': [],  # marketplace fees/tips are not restaurant revenue
            'discounts': discounts,
            'raw': payload,
        }

    @staticmethod
    def _money(container, key):
        """Extract a money amount (minor units) from Uber's nested shapes."""
        if not isinstance(container, dict):
            return 0.0
        value = container.get(key)
        if isinstance(value, dict):
            value = value.get('amount', 0)
        return (value or 0) / 100.0
