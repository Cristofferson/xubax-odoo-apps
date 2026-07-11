# -*- coding: utf-8 -*-
"""DiDi Food Open Platform driver (Mexico / LatAm).

Docs: https://developer.didi-food.com (Open Platform, v1/v3 endpoints).
Auth: per-store auth_token (GET /v1/auth/authtoken/get, ~30 day validity).
Money: integer cents (MXN centavos).
Webhook: header didi-header-sign = MD5(raw body + app_secret); the endpoint
must answer {"errno": 0, "errmsg": "ok"} within 6 seconds.
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta

from odoo import fields, _
from odoo.tools import consteq

from .base_driver import BaseDeliveryDriver, DeliveryDriverError, register_driver

_logger = logging.getLogger(__name__)

API_BASE = 'https://openapi.didi-food.com'

# Cancel reasons (POST /v1/order/order/cancel).
REASON_SOLD_OUT = 1010
REASON_CLOSED = 1020
REASON_TOO_BUSY = 1030
REASON_OTHER = 1080

ORDER_STATUS_MAP = {
    100: 'placed',
    200: 'accepted',
    400: 'dispatched',
    500: 'dispatched',
    600: 'delivered',
}
CANCEL_STATUSES = {901, 902, 921, 922, 923, 961, 971, 981}


@register_driver('didi_food')
class DidiFoodDriver(BaseDeliveryDriver):

    # ------------------------------------------------------------------
    # Auth: per-store auth_token
    # ------------------------------------------------------------------

    def _auth_params(self):
        account = self.account
        return {
            'app_id': account.client_id,
            'app_secret': account.client_secret,
            'app_shop_id': account.external_store_id,
        }

    def _get_token(self, force=False):
        account = self.account
        if (not force and account.access_token and account.token_expiry
                and account.token_expiry > fields.Datetime.now() + timedelta(days=1)):
            return account.access_token
        data = self._call('GET', '/v1/auth/authtoken/get',
                          params=self._auth_params(), use_token=False,
                          errno_ok=(0, 10102))
        if data.get('_errno') == 10102:
            # Expired: refresh, then get again.
            self._call('GET', '/v1/auth/authtoken/refresh',
                       params=self._auth_params(), use_token=False)
            data = self._call('GET', '/v1/auth/authtoken/get',
                              params=self._auth_params(), use_token=False)
        token = data.get('auth_token')
        if not token:
            raise DeliveryDriverError(_('DiDi Food did not return an auth_token.'))
        expiry = data.get('token_expiration_time')
        account.write({
            'access_token': token,
            'token_expiry': datetime.utcfromtimestamp(expiry) if expiry
            else fields.Datetime.now() + timedelta(days=25),
        })
        return token

    def _call(self, method, path, params=None, body=None, use_token=True,
              log_event=None, errno_ok=(0,)):
        """Call a DiDi endpoint and unwrap the {errno, errmsg, data} envelope."""
        kwargs = {}
        if params:
            kwargs['params'] = params
        if use_token:
            body = dict(body or {})
            body['auth_token'] = self._get_token()
        if body is not None:
            kwargs['json'] = body
        response = self._request(method, API_BASE + path,
                                 log_event=log_event, **kwargs)
        if not response.ok:
            raise DeliveryDriverError(
                'DiDi Food HTTP %s on %s' % (response.status_code, path))
        try:
            envelope = response.json()
        except ValueError as exc:
            raise DeliveryDriverError('DiDi Food: invalid JSON response.') from exc
        errno = envelope.get('errno')
        if errno == 10102 and use_token:
            # Token expired server-side: force renewal and retry once.
            body['auth_token'] = self._get_token(force=True)
            return self._call(method, path, params=params,
                              body={k: v for k, v in body.items()
                                    if k != 'auth_token'},
                              use_token=use_token, log_event=log_event,
                              errno_ok=errno_ok)
        if errno not in errno_ok:
            raise DeliveryDriverError(
                'DiDi Food error %s on %s: %s'
                % (errno, path, envelope.get('errmsg')))
        data = envelope.get('data') or {}
        if isinstance(data, dict):
            data['_errno'] = errno
        return data

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    def test_connection(self):
        self._get_token(force=True)
        return _('Connected to DiDi Food (store %s authorized).',
                 self.account.external_store_id)

    def push_menu(self, snapshot):
        payload = self._build_menu_payload(snapshot)
        self._call('POST', '/v3/item/item/upload', body=payload,
                   log_event='didi_menu_upload')
        return _('%s items sent to DiDi Food (asynchronous processing; the '
                 'result arrives by webhook).', len(snapshot['items']))

    def set_store_status(self, online):
        self._call('POST', '/v1/shop/shop/setStatus', body={
            'biz_status': 1 if online else 2,
            'auto_switch': 1,
        })
        return True

    def set_item_availability(self, template, available):
        self._call('POST', '/v3/item/item/updateItemStatus', body={
            'app_item_ids': [str(template.id)],
            'status': 1 if available else 2,
        })
        return True

    def accept_order(self, order):
        self._call('POST', '/v1/order/order/confirm',
                   body={'order_id': int(order.xb_delivery_identifier)})
        return True

    def deny_order(self, order, reason):
        reason_lower = (reason or '').lower()
        if 'closed' in reason_lower or 'cerrad' in reason_lower:
            reason_id = REASON_CLOSED
        elif 'stock' in reason_lower or 'agotad' in reason_lower:
            reason_id = REASON_SOLD_OUT
        else:
            reason_id = REASON_OTHER
        self._call('POST', '/v1/order/order/cancel', body={
            'order_id': int(order.xb_delivery_identifier),
            'reason_id': reason_id,
        })
        return True

    def cancel_order(self, order, reason=None):
        return self.deny_order(order, reason)

    def mark_ready(self, order):
        self._call('POST', '/v1/order/order/ready',
                   body={'order_id': int(order.xb_delivery_identifier)})
        return True

    def confirm_cash_payment(self, order):
        self._call('POST', '/v1/order/order/payConfirm',
                   body={'order_id': int(order.xb_delivery_identifier)})
        return True

    def get_order(self, order_id):
        return self._call('GET', '/v1/order/order/detail', params={
            'auth_token': self._get_token(),
            'order_id': order_id,
        }, use_token=False)

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------

    def verify_webhook(self, headers, raw_body):
        signature = headers.get('didi-header-sign') or ''
        secret = (self.account.client_secret or '').encode()
        expected = hashlib.md5(raw_body + secret).hexdigest()
        return bool(signature) and consteq(expected, signature.lower())

    # ------------------------------------------------------------------
    # Payload conversions
    # ------------------------------------------------------------------

    @staticmethod
    def _cents(amount):
        return int(round((amount or 0.0) * 100))

    def _tax_info(self):
        """Mexico: IVA must be 0 or 1600 basis points."""
        company = self.account.company_id
        if company.country_id and company.country_id.code != 'MX':
            return []
        taxes = self.env['account.tax'].sudo().search([
            ('company_id', '=', company.id),
            ('type_tax_use', '=', 'sale'),
            ('amount_type', '=', 'percent'),
        ], limit=1)
        rate = 1600 if taxes and round(taxes.amount) == 16 else 0
        return [{'type': 1, 'rate': rate}]

    def _build_menu_payload(self, snapshot):
        tax_info = self._tax_info()
        categories = []
        for cat in snapshot['categories']:
            item_ids = [item['ref'] for item in snapshot['items']
                        if item['category_ref'] == cat['ref']]
            if item_ids:
                categories.append({
                    'app_category_id': cat['ref'],
                    'category_name': (cat['name'] or 'Menu')[:100],
                    'app_item_ids': item_ids,
                })
        items = []
        for item in snapshot['items']:
            entry = {
                'app_item_id': item['ref'],
                'app_external_id': json.dumps({'odoo_tmpl_id': item['ref']}),
                'item_name': (item['name'] or '')[:50],
                'short_desc': (item['description'] or '')[:400],
                'price': self._cents(item['price']),
                'status': 1 if item['available'] else 2,
                'is_sold_separately': True,
                'app_modifier_group_ids': item['modifier_group_refs'],
            }
            if tax_info:
                entry['tax_info_list'] = tax_info
            if item.get('image_url'):
                entry['head_img'] = item['image_url']
            items.append(entry)
        modifier_groups = []
        for group in snapshot['modifier_groups']:
            modifier_groups.append({
                'app_modifier_group_id': group['ref'],
                'modifier_group_name': (group['name'] or '')[:100],
                'is_required': 1 if group['min_permitted'] else 2,
                'quantity_min_permitted': group['min_permitted'],
                'quantity_max_permitted': group['max_permitted'],
                'buy_mode': 0,
                'app_mg_items': [{
                    'app_item_id': opt['ref'],
                    'price': self._cents(opt['price']),
                } for opt in group['options']],
            })
            # Modifier options must exist as (non separately sold) items.
            for opt in group['options']:
                entry = {
                    'app_item_id': opt['ref'],
                    'item_name': (opt['name'] or '')[:50],
                    'price': self._cents(opt['price']),
                    'status': 1,
                    'is_sold_separately': False,
                }
                if tax_info:
                    entry['tax_info_list'] = tax_info
                items.append(entry)
        return {
            'menus': [{'app_menu_id': 'menu-odoo',
                       'menu_name': 'Menu'}],
            'categories': categories,
            'items': items,
            'modifier_groups': modifier_groups,
        }

    def parse_order(self, payload):
        """Normalize an orderNew webhook / order detail payload."""
        info = payload.get('order_info') or payload
        price = info.get('price') or {}
        items = []
        for line in info.get('order_items') or []:
            qty = line.get('amount') or 1
            options = []
            extra_per_unit = 0.0
            for sub in line.get('sub_item_list') or []:
                sub_qty = sub.get('amount') or 1
                sub_price = (sub.get('sku_price') or 0) / 100.0
                options.append({
                    'ref': str(sub.get('app_item_id') or ''),
                    'name': sub.get('name') or '',
                    'qty': sub_qty,
                    'price': sub_price,
                })
                extra_per_unit += sub_price * sub_qty
            remark = line.get('remark')
            if isinstance(remark, (list, tuple)):
                remark = '\n'.join(str(r) for r in remark)
            item_ref = str(line.get('app_item_id') or '')
            external = line.get('app_external_id')
            if external:
                try:
                    item_ref = str(json.loads(external).get('odoo_tmpl_id')
                                   or item_ref)
                except (ValueError, AttributeError):
                    pass
            items.append({
                'ref': item_ref,
                'name': line.get('name') or '',
                'qty': qty,
                'unit_price': (line.get('sku_price') or 0) / 100.0 + extra_per_unit,
                'options': options,
                'note': remark or '',
            })
        # Cash handling (see docs): DiDi delivery -> courier pays the store
        # (shop_paid_money); store delivery -> customer pays the store.
        pay_type = info.get('pay_type')
        cash_due = 0.0
        if pay_type == 2:
            cash_due = (price.get('shop_paid_money')
                        or price.get('customer_need_paying_money') or 0) / 100.0
        charges = []
        # Fees settled to the store.
        if price.get('meal_top_up_price'):
            charges.append({'type': 'other', 'name': _('Minimum order top-up'),
                            'amount': price['meal_top_up_price'] / 100.0})
        if info.get('delivery_type') == 2 and price.get('delivery_price'):
            # Self-delivery: the delivery fee belongs to the store.
            charges.append({'type': 'delivery', 'name': _('Delivery fee'),
                            'amount': price['delivery_price'] / 100.0})
        if info.get('delivery_type') == 2 and price.get('total_tip_money'):
            charges.append({'type': 'tip', 'name': _('Courier tip'),
                            'amount': price['total_tip_money'] / 100.0})
        discounts = []
        for line in info.get('order_items') or []:
            for promo in (line.get('promotion_detail') or []):
                shop_part = (promo.get('shop_subside_price') or 0) / 100.0
                if shop_part:
                    discounts.append({
                        'title': _('DiDi promotion (store funded)'),
                        'code': str(promo.get('promo_type') or ''),
                        'amount': shop_part,
                        'restaurant_funded': True,
                    })
        prep_time = None
        if info.get('expected_cook_eta'):
            prep_time = max(1, int(info['expected_cook_eta'] / 60))
        receive = info.get('receive_address') or {}
        customer_name = (receive.get('user_name')
                         or receive.get('poi_display_name') or '')
        return {
            'external_id': str(info.get('order_id')),
            'display_id': str(info.get('order_index') or info.get('order_id')),
            'type': 'pickup' if info.get('fulfillment_mode') == 1 else 'delivery',
            'note': info.get('remark') or '',
            'prep_time': prep_time,
            'cash_due': cash_due,
            'customer': {
                'name': customer_name or 'DiDi Food #%s' % (info.get('order_index') or ''),
                'phone': info.get('virtual_phone_number') or '',
                'street': receive.get('poi_display_name') or '',
                'city': receive.get('city_name') or '',
            },
            'items': items,
            'charges': charges,
            'discounts': discounts,
            'raw': payload,
        }

    @staticmethod
    def map_status(didi_status):
        if didi_status in CANCEL_STATUSES:
            return 'cancelled'
        return ORDER_STATUS_MAP.get(didi_status)
