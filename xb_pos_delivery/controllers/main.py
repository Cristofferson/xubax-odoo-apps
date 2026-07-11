# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request
from odoo.tools import consteq

_logger = logging.getLogger(__name__)

DIDI_OK = json.dumps({'errno': 0, 'errmsg': 'ok'})
DIDI_ERR = json.dumps({'errno': 1, 'errmsg': 'error'})

# DiDi courier states (deliveryStatus webhook).
DIDI_RIDER_TAKEN = 140
DIDI_RIDER_FINISH = 160


class XbDeliveryController(http.Controller):

    def _get_account(self, account_id, secret):
        account = request.env['xb.delivery.account'].sudo().browse(account_id).exists()
        if not account or not consteq(account.webhook_secret or '', secret):
            return None
        return account

    def _route_account(self, account, store_id):
        """Webhook URLs are per-app on both platforms: when a multi-branch
        restaurant shares one app, route the event to the sibling account
        matching the store id in the payload."""
        if not store_id or account.external_store_id == str(store_id):
            return account
        sibling = request.env['xb.delivery.account'].sudo().search([
            ('provider', '=', account.provider),
            ('client_id', '=', account.client_id),
            ('external_store_id', '=', str(store_id)),
        ], limit=1)
        return sibling or account

    # ------------------------------------------------------------------
    # Webhook endpoint (both providers)
    # ------------------------------------------------------------------

    @http.route('/xb_delivery/<int:account_id>/<string:secret>/webhook',
                type='http', auth='public', methods=['POST'], csrf=False,
                save_session=False)
    def webhook(self, account_id, secret, **kwargs):
        account = self._get_account(account_id, secret)
        if not account:
            _logger.warning('xb_delivery: webhook for unknown account %s', account_id)
            return request.make_json_response({'error': 'unknown'}, status=404)
        raw_body = request.httprequest.get_data()
        driver = account._get_driver()
        if not driver.verify_webhook(request.httprequest.headers, raw_body):
            account._log('in', 'webhook_rejected', success=False,
                         message='Invalid signature')
            return request.make_json_response({'error': 'signature'}, status=403)
        try:
            payload = json.loads(raw_body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            account._log('in', 'webhook_rejected', success=False,
                         message='Invalid JSON body')
            return request.make_json_response({'error': 'body'}, status=400)

        try:
            if account.provider == 'uber_eats':
                self._handle_uber(account, payload)
                return request.make_json_response({})
            if account.provider == 'didi_food':
                self._handle_didi(account, payload)
                return request.make_response(
                    DIDI_OK, headers=[('Content-Type', 'application/json')])
        except Exception:  # noqa: BLE001
            _logger.exception('xb_delivery: webhook processing failed')
            account._log('in', 'webhook_error', payload=payload, success=False,
                         message='Processing exception; see server log')
            # 500 so the platform retries.
            body = DIDI_ERR if account.provider == 'didi_food' else '{}'
            return request.make_response(
                body, headers=[('Content-Type', 'application/json')], status=500)
        return request.make_json_response({})

    # ------------------------------------------------------------------
    # Uber Eats events
    # ------------------------------------------------------------------

    def _handle_uber(self, account, payload):
        event_type = payload.get('event_type') or ''
        meta = payload.get('meta') or {}
        account = self._route_account(account, meta.get('user_id'))
        if event_type == 'orders.notification':
            order_id = meta.get('resource_id')
            if not order_id:
                account._log('in', event_type, payload=payload, success=False,
                             message='Missing meta.resource_id')
                return
            details = account._get_driver().get_order(order_id)
            norm = account._get_driver().parse_order(details)
            self._process_or_reject(account, norm)
        elif event_type in ('orders.cancel', 'orders.failure'):
            order = self._find_order(account, meta.get('resource_id'))
            if order:
                order._xb_cancel_locally()
                account._bus_order_event(order)
            account._log('in', event_type, payload=payload, success=True)
        elif event_type == 'store.menu_refresh_request':
            account._log('in', event_type, success=True,
                         message='Platform requested a menu re-sync')
            try:
                account.action_sync_menu()
            except Exception as exc:  # noqa: BLE001
                _logger.warning('xb_delivery: auto menu refresh failed: %s', exc)
        elif event_type == 'store.provisioned':
            account.write({'state': 'connected',
                           'connection_msg': 'Store provisioned by Uber Eats'})
            account._log('in', event_type, payload=payload, success=True)
        elif event_type == 'store.deprovisioned':
            account.write({'state': 'draft',
                           'connection_msg': 'Store deprovisioned by Uber Eats'})
            account._log('in', event_type, payload=payload, success=True)
        else:
            account._log('in', event_type or 'unknown', payload=payload,
                         success=True, message='Unhandled event type')

    # ------------------------------------------------------------------
    # DiDi Food events
    # ------------------------------------------------------------------

    def _handle_didi(self, account, payload):
        event_type = payload.get('type') or ''
        account = self._route_account(account, payload.get('app_shop_id'))
        data = payload.get('data')
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                data = {}
        data = data or {}
        if event_type == 'orderNew':
            norm = account._get_driver().parse_order(data)
            self._process_or_reject(account, norm)
        elif event_type in ('orderCancel', 'orderPartialCancel'):
            order = self._find_order(account, self._didi_order_id(data))
            if order and event_type == 'orderCancel':
                order._xb_cancel_locally()
                account._bus_order_event(order)
            account._log('in', event_type, payload=data, success=True)
        elif event_type == 'orderFinish':
            order = self._find_order(account, self._didi_order_id(data))
            if order:
                order._xb_set_status('delivered')
                if order.state == 'draft':
                    order._xb_register_payment()
                account._bus_order_event(order)
            account._log('in', event_type, success=True)
        elif event_type == 'deliveryStatus':
            self._didi_delivery_status(account, data)
        elif event_type in ('orderCancelApply', 'orderRefundApply'):
            # Customer requests need human review; surface them in the log
            # and on the order chatter. (Cancel requests auto-refuse and
            # refund requests auto-agree on DiDi timeout.)
            order = self._find_order(account, self._didi_order_id(data))
            if order:
                order.message_post(body=(
                    'DiDi Food: %s received. Review it in the DiDi store app.'
                    % event_type))
            account._log('in', event_type, payload=data, success=True,
                         message='Needs review in the DiDi store app')
        elif event_type == 'uploadMenuTaskStatus':
            failed = data.get('failed_items') or data.get('fail_items') or []
            account.write({'menu_last_result':
                           'DiDi: menu processed, %s rejected items' % len(failed)
                           if failed else 'DiDi: menu published'})
            account._log('in', event_type, payload=data, success=not failed)
        elif event_type == 'shopStatus':
            account._log('in', event_type, payload=data, success=True)
        else:
            account._log('in', event_type or 'unknown', payload=data,
                         success=True, message='Unhandled event type')

    @staticmethod
    def _didi_order_id(data):
        info = data.get('order_info') or data
        return info.get('order_id')

    def _didi_delivery_status(self, account, data):
        order = self._find_order(account, self._didi_order_id(data))
        if not order:
            account._log('in', 'deliveryStatus', payload=data, success=False,
                         message='Order not found')
            return
        courier = {
            'name': data.get('rider_name') or '',
            'phone': data.get('rider_phone') or '',
            'eta': data.get('rider_to_B_ETA') or '',
            'state': data.get('status') or data.get('delivery_status') or '',
        }
        order.xb_courier_json = json.dumps(courier)
        state = courier['state']
        if state == DIDI_RIDER_TAKEN:
            order._xb_set_status('dispatched')
            if order.state == 'draft':
                order._xb_register_payment()
        elif state == DIDI_RIDER_FINISH:
            order._xb_set_status('delivered')
        account._bus_order_event(order)
        account._log('in', 'deliveryStatus', success=True,
                     message='%s (%s)' % (courier['name'], state))

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _find_order(self, account, external_id):
        if not external_id:
            return request.env['pos.order'].sudo()
        return request.env['pos.order'].sudo().search([
            ('xb_delivery_account_id', '=', account.id),
            ('xb_delivery_identifier', '=', str(external_id)),
        ], limit=1)

    def _process_or_reject(self, account, norm):
        session = account.config_id.current_session_id
        if not session or session.state != 'opened':
            account._log('in', 'order_placed', payload=norm.get('raw'),
                         success=False, message='No open POS session')
            if account.closed_session_policy == 'reject':
                try:
                    account._get_driver().deny_order(
                        self._stub_order(account, norm), 'Store closed')
                    account._log('out', 'deny_order', success=True,
                                 message='%s (store closed)' % norm['external_id'])
                except Exception as exc:  # noqa: BLE001
                    account._log('out', 'deny_order', success=False,
                                 message=str(exc))
            return
        account._process_incoming_order(norm)

    def _stub_order(self, account, norm):
        """Lightweight stand-in so drivers can deny an order that was never
        created in Odoo (no open session)."""
        return type('StubOrder', (), {
            'xb_delivery_identifier': norm['external_id'],
            'pos_reference': '',
        })()

    # ------------------------------------------------------------------
    # Public product images for platform menus
    # ------------------------------------------------------------------

    @http.route('/xb_delivery/img/<int:account_id>/<string:secret>/<int:tmpl_id>',
                type='http', auth='public', methods=['GET'], csrf=False,
                save_session=False)
    def menu_image(self, account_id, secret, tmpl_id, **kwargs):
        account = self._get_account(account_id, secret)
        if not account:
            return request.not_found()
        template = request.env['product.template'].sudo().browse(tmpl_id).exists()
        if not template or not template.image_1920:
            return request.not_found()
        return request.env['ir.binary']._get_image_stream_from(
            template, field_name='image_1024').get_response()
