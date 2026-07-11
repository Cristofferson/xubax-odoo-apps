# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import XbDeliveryCommon


@tagged('post_install', '-at_install')
class TestMenuBuilder(XbDeliveryCommon):

    def test_snapshot_structure(self):
        snapshot = self.account_uber._build_menu_snapshot()
        refs = {item['ref'] for item in snapshot['items']}
        self.assertIn(str(self.taco.id), refs)
        self.assertIn(str(self.agua.id), refs)
        taco = next(i for i in snapshot['items'] if i['ref'] == str(self.taco.id))
        # list_price is tax included: menu price must stay 100.00
        self.assertAlmostEqual(taco['price'], 100.0, places=2)
        self.assertTrue(taco['modifier_group_refs'])
        group = snapshot['modifier_groups'][0]
        self.assertEqual(group['name'], 'Salsa')
        self.assertEqual(len(group['options']), 2)
        self.assertEqual(group['min_permitted'], 1)
        self.assertEqual(group['max_permitted'], 1)

    def test_snapshot_pricelist(self):
        pricelist = self.env['product.pricelist'].create({
            'name': 'Delivery +20%',
            'company_id': self.company.id,
            'currency_id': self.company_currency.id,
            'item_ids': [(0, 0, {
                'compute_price': 'percentage',
                'percent_price': -20,  # surcharge
            })],
        })
        self.account_uber.pricelist_id = pricelist
        snapshot = self.account_uber._build_menu_snapshot()
        taco = next(i for i in snapshot['items'] if i['ref'] == str(self.taco.id))
        self.assertAlmostEqual(taco['price'], 120.0, places=2)

    def test_uber_payload(self):
        driver = self.account_uber._get_driver()
        payload = driver._build_menu_payload(
            self.account_uber._build_menu_snapshot())
        self.assertEqual(len(payload['menus']), 1)
        item = next(i for i in payload['items'] if i['id'] == str(self.taco.id))
        self.assertEqual(item['price_info']['price'], 10000)  # centavos
        self.assertTrue(payload['categories'])
        self.assertTrue(payload['modifier_groups'])
        group = payload['modifier_groups'][0]
        option_ids = [opt['id'] for opt in group['modifier_options']]
        # Options exist as items too
        payload_item_ids = [i['id'] for i in payload['items']]
        for option_id in option_ids:
            self.assertIn(option_id, payload_item_ids)

    def test_didi_payload(self):
        driver = self.account_didi._get_driver()
        payload = driver._build_menu_payload(
            self.account_didi._build_menu_snapshot())
        item = next(i for i in payload['items']
                    if i['app_item_id'] == str(self.taco.id))
        self.assertEqual(item['price'], 10000)
        self.assertEqual(item['status'], 1)
        self.assertTrue(item['is_sold_separately'])
        group = payload['modifier_groups'][0]
        self.assertEqual(group['is_required'], 1)
        self.assertEqual(group['buy_mode'], 0)
        # Options must exist as non-separately-sold items
        option_id = group['app_mg_items'][0]['app_item_id']
        option_item = next(i for i in payload['items']
                           if i['app_item_id'] == option_id)
        self.assertFalse(option_item['is_sold_separately'])

    def test_sold_out_in_snapshot(self):
        self.env['xb.delivery.item.status'].with_context(
            xb_skip_push=True).create({
                'account_id': self.account_uber.id,
                'product_tmpl_id': self.taco.id,
                'is_available': False,
            })
        snapshot = self.account_uber._build_menu_snapshot()
        taco = next(i for i in snapshot['items'] if i['ref'] == str(self.taco.id))
        self.assertFalse(taco['available'])
