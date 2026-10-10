# -*- coding: utf-8 -*-
from odoo.fields import Domain
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTagGroups(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].create({'name': 'Tag groups test'})
        Group = cls.env['product.tag.group']
        Tag = cls.env['product.tag']
        cls.style = Group.create({'name': 'XB Style', 'sequence': 1})
        cls.stones = Group.create({'name': 'XB Stones', 'sequence': 2})
        cls.eternity = Tag.create({'name': 'XB Eternity', 'filter_group_id': cls.style.id})
        cls.promise = Tag.create({'name': 'XB Promise', 'filter_group_id': cls.style.id})
        cls.solitaire = Tag.create({'name': 'XB Solitaire', 'filter_group_id': cls.stones.id})
        cls.loose = Tag.create({'name': 'XB New'})

        def product(name, tags):
            return cls.env['product.template'].create({
                'name': name, 'is_published': True, 'website_id': cls.website.id,
                'product_tag_ids': [(6, 0, tags.ids)],
            })
        cls.p_eternity_solitaire = product('XB Ring A', cls.eternity | cls.solitaire)
        cls.p_promise = product('XB Ring B', cls.promise)
        cls.p_eternity_promise = product('XB Ring C', cls.eternity | cls.promise | cls.loose)
        cls.all_products = cls.p_eternity_solitaire | cls.p_promise | cls.p_eternity_promise

    def _search(self, tags):
        options = {
            'displayDescription': False, 'displayDetail': False, 'displayExtraDetail': False,
            'displayExtraLink': False, 'displayImage': False, 'allowFuzzy': False,
            'category': None, 'min_price': 0, 'max_price': 0, 'attribute_value_dict': None,
            'display_currency': self.website.currency_id,
            'tags': ','.join(str(t.id) for t in tags) if tags else None,
        }
        detail = self.env['product.template']._search_get_detail(self.website, 'name asc', options)
        # The first domain is the website's own product domain (company, publication…), not
        # what this module tests.
        self.assertEqual(detail['base_domain'][0], self.website.sale_product_domain())
        domain = Domain.AND(detail['base_domain'][1:] + [[('id', 'in', self.all_products.ids)]])
        return self.env['product.template'].search(domain)

    def test_buckets(self):
        tags = self.eternity | self.promise | self.solitaire | self.loose
        buckets = tags._xb_filter_buckets()
        self.assertEqual([b[0] for b in buckets],
                         ['tags', 'tag_group_%s' % self.style.id, 'tag_group_%s' % self.stones.id])
        self.assertEqual(buckets[0][2], self.loose)
        self.assertEqual(buckets[1][2], self.eternity | self.promise)
        self.assertEqual(buckets[2][2], self.solitaire)

    def test_same_group_is_or(self):
        self.assertEqual(self._search(self.eternity | self.promise), self.all_products)

    def test_different_groups_is_and(self):
        self.assertEqual(self._search(self.eternity | self.solitaire), self.p_eternity_solitaire)
        self.assertEqual(self._search(self.promise | self.solitaire), self.env['product.template'])

    def test_ungrouped_tags_still_work(self):
        self.assertEqual(self._search(self.loose), self.p_eternity_promise)
        self.assertEqual(self._search(self.loose | self.promise), self.p_eternity_promise)
        self.assertEqual(self._search(self.loose | self.solitaire), self.env['product.template'])
