# -*- coding: utf-8 -*-
import hashlib
import hmac
import json

from odoo.tests import HttpCase, tagged

from .common import XbDeliveryCommon


@tagged('post_install', '-at_install')
class TestWebhooks(XbDeliveryCommon, HttpCase):

    def _didi_payload(self):
        return {
            'app_id': 1152921557674426642,
            'app_shop_id': 'shop-1',
            'type': 'orderNew',
            'timestamp': 1760000000,
            'data': {
                'order_info': {
                    'order_id': 5764607801871631353,
                    'order_index': 7,
                    'status': 100,
                    'fulfillment_mode': 0,
                    'delivery_type': 1,
                    'pay_type': 1,
                    'remark': 'Tocar el timbre',
                    'expected_cook_eta': 900,
                    'virtual_phone_number': '5588990011',
                    'receive_address': {'poi_display_name': 'Col. Centro'},
                    'price': {},
                    'order_items': [{
                        'app_item_id': str(self.taco.id),
                        'name': 'Taco Pastor',
                        'amount': 2,
                        'sku_price': 10000,
                        'total_price': 20000,
                        'sub_item_list': [],
                        'promotion_detail': [],
                    }],
                },
            },
        }

    def _didi_post(self, payload, secret='didi-secret'):
        body = json.dumps(payload).encode()
        sign = hashlib.md5(body + secret.encode()).hexdigest()
        url = '/xb_delivery/%s/%s/webhook' % (
            self.account_didi.id, self.account_didi.webhook_secret)
        return self.url_open(url, data=body, headers={
            'Content-Type': 'application/json',
            'didi-header-sign': sign,
        })

    def test_didi_order_new_creates_pos_order(self):
        self.open_new_session()
        response = self._didi_post(self._didi_payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'errno': 0, 'errmsg': 'ok'})
        order = self.env['pos.order'].search([
            ('xb_delivery_identifier', '=', '5764607801871631353')])
        self.assertTrue(order)
        self.assertEqual(order.xb_delivery_account_id, self.account_didi)
        self.assertEqual(order.xb_delivery_display_id, '7')
        self.assertAlmostEqual(order.amount_total, 200.0, places=2)
        self.assertEqual(order.xb_prep_time, 15)

    def test_didi_bad_signature_rejected(self):
        self.open_new_session()
        response = self._didi_post(self._didi_payload(), secret='wrong')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.env['pos.order'].search([
            ('xb_delivery_identifier', '=', '5764607801871631353')]))

    def test_bad_url_secret_rejected(self):
        body = json.dumps(self._didi_payload()).encode()
        url = '/xb_delivery/%s/not-the-secret/webhook' % self.account_didi.id
        response = self.url_open(url, data=body, headers={
            'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 404)

    def test_uber_signature_verification(self):
        driver = self.account_uber._get_driver()
        body = b'{"event_type": "orders.notification"}'
        good = hmac.new(b'test-secret', body, hashlib.sha256).hexdigest()
        self.assertTrue(driver.verify_webhook({'X-Uber-Signature': good}, body))
        self.assertFalse(driver.verify_webhook({'X-Uber-Signature': 'bad'}, body))
        self.assertFalse(driver.verify_webhook({}, body))

    def test_didi_status_and_cancel_flow(self):
        self.open_new_session()
        self._didi_post(self._didi_payload())
        order = self.env['pos.order'].search([
            ('xb_delivery_identifier', '=', '5764607801871631353')])
        # Courier takes the order -> dispatched + payment registered
        payload = self._didi_payload()
        payload['type'] = 'deliveryStatus'
        payload['data'] = {
            'order_id': 5764607801871631353,
            'status': 140,
            'rider_name': 'Pedro Repartidor',
            'rider_phone': '5522334455',
        }
        response = self._didi_post(payload)
        self.assertEqual(response.status_code, 200)
        order.invalidate_recordset()
        self.assertEqual(order.xb_delivery_status, 'dispatched')
        self.assertEqual(order.state, 'paid')
        courier = order.get_xb_courier_info()
        self.assertEqual(courier['name'], 'Pedro Repartidor')

    def test_didi_order_cancel(self):
        self.open_new_session()
        self._didi_post(self._didi_payload())
        payload = self._didi_payload()
        payload['type'] = 'orderCancel'
        response = self._didi_post(payload)
        self.assertEqual(response.status_code, 200)
        order = self.env['pos.order'].search([
            ('xb_delivery_identifier', '=', '5764607801871631353')])
        self.assertEqual(order.xb_delivery_status, 'cancelled')
        self.assertEqual(order.state, 'cancel')
