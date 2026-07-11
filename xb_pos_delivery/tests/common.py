# -*- coding: utf-8 -*-
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


class XbDeliveryCommon(TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        cls.tax_16_incl = cls.env['account.tax'].create({
            'name': 'IVA 16% incl',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include_override': 'tax_included',
            'company_id': cls.company.id,
        })
        cls.categ_tacos = cls.env['pos.category'].create({'name': 'Tacos'})
        cls.attr_salsa = cls.env['product.attribute'].create({
            'name': 'Salsa',
            'create_variant': 'no_variant',
        })
        cls.attr_val_verde = cls.env['product.attribute.value'].create({
            'name': 'Verde', 'attribute_id': cls.attr_salsa.id,
        })
        cls.attr_val_roja = cls.env['product.attribute.value'].create({
            'name': 'Roja', 'attribute_id': cls.attr_salsa.id,
        })
        cls.taco = cls.env['product.template'].create({
            'name': 'Taco Pastor',
            'type': 'consu',
            'available_in_pos': True,
            'list_price': 100.0,  # tax included -> 100.00 MXN-ish
            'taxes_id': [(6, 0, cls.tax_16_incl.ids)],
            'pos_categ_ids': [(6, 0, cls.categ_tacos.ids)],
            'attribute_line_ids': [(0, 0, {
                'attribute_id': cls.attr_salsa.id,
                'value_ids': [(6, 0, [cls.attr_val_verde.id, cls.attr_val_roja.id])],
            })],
        })
        cls.agua = cls.env['product.template'].create({
            'name': 'Agua de Horchata',
            'type': 'consu',
            'available_in_pos': True,
            'list_price': 35.0,
            'taxes_id': [(6, 0, cls.tax_16_incl.ids)],
            'pos_categ_ids': [(6, 0, cls.categ_tacos.ids)],
        })
        cls.account_uber = cls.env['xb.delivery.account'].create({
            'provider': 'uber_eats',
            'config_id': cls.config.id,
            'client_id': 'test-client',
            'client_secret': 'test-secret',
            'external_store_id': 'store-uuid-1',
        })
        cls.account_didi = cls.env['xb.delivery.account'].create({
            'provider': 'didi_food',
            'config_id': cls.config.id,
            'client_id': '1152921557674426642',
            'client_secret': 'didi-secret',
            'external_store_id': 'shop-1',
        })

    def _norm_order(self, external_id='ORD-1', **overrides):
        taco_ptav = self.taco.attribute_line_ids.product_template_value_ids[0]
        norm = {
            'external_id': external_id,
            'display_id': external_id[-5:],
            'type': 'delivery',
            'note': 'Sin cebolla',
            'prep_time': 15,
            'cash_due': 0.0,
            'customer': {'name': 'Juan Prueba', 'phone': '5511122233'},
            'items': [
                {
                    'ref': str(self.taco.id),
                    'name': 'Taco Pastor',
                    'qty': 3,
                    'unit_price': 100.0,
                    'options': [{
                        'ref': 'ptav-%s' % taco_ptav.id,
                        'name': 'Verde',
                        'qty': 1,
                        'price': 0.0,
                    }],
                    'note': 'Con todo',
                },
                {
                    'ref': str(self.agua.id),
                    'name': 'Agua de Horchata',
                    'qty': 1,
                    'unit_price': 35.0,
                    'options': [],
                    'note': '',
                },
            ],
            'charges': [],
            'discounts': [],
            'raw': {'test': True},
        }
        norm.update(overrides)
        return norm
