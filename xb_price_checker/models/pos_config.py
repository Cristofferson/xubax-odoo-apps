import secrets

from odoo import _, api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    price_checker_token = fields.Char(
        string="Price checker key", copy=False, groups='point_of_sale.group_pos_manager',
        help="Secret part of the link of the price checker. Change it to stop the screens that have the old link.")
    price_checker_show_stock = fields.Boolean(
        string="Show stock", default=True,
        help="Tell the customer whether this store has the product (without the number of pieces).")
    price_checker_show_months = fields.Boolean(
        string="Show months without interest", default=True,
        help="Months without interest of the payment rules, when a module that has them is installed (XPago).")
    price_checker_idle = fields.Integer(
        string="Back to the start after (seconds)", default=15,
        help="Seconds a product stays on screen before the welcome screen comes back.")
    price_checker_url = fields.Char(string="Price checker link", compute='_compute_price_checker_url')

    @api.depends('price_checker_token')
    def _compute_price_checker_url(self):
        base = self.get_base_url()
        for config in self:
            config.price_checker_url = (
                f"{base}/price-checker/{config.id}/{config.sudo().price_checker_token}"
                if config.id and config.sudo().price_checker_token else False)

    def action_price_checker_new_link(self):
        """A new secret link: the screens with the old one stop working."""
        for config in self:
            config.sudo().price_checker_token = secrets.token_urlsafe(18)

    def action_price_checker_open(self):
        self.ensure_one()
        if not self.sudo().price_checker_token:
            self.action_price_checker_new_link()
        return {'type': 'ir.actions.act_url', 'url': self.price_checker_url, 'target': 'new'}

    # What the screen shows

    def _price_checker_product(self, code):
        """The product with this barcode, or else this internal reference, that this store sells."""
        self.ensure_one()
        code = (code or '').strip()
        if not code or len(code) > 256:
            return self.env['product.product']
        Product = self.env['product.product'].sudo().with_company(self.company_id)
        domain = [('sale_ok', '=', True), ('company_id', 'in', [False, *self.company_id.parent_ids.ids])]
        return Product.search([('barcode', '=', code)] + domain, limit=1) \
            or Product.search([('default_code', '=ilike', code)] + domain, limit=1)

    def _price_checker_lang(self):
        """The language of the store's screens: the company's."""
        return self.sudo().company_id.partner_id.lang or self.env.lang or 'en_US'

    def _price_checker_info(self, code):
        """What the price checker shows for ``code`` (a barcode or an internal reference)."""
        self.ensure_one()
        config = self.sudo().with_context(lang=self._price_checker_lang())
        product = config._price_checker_product(code)
        if not product:
            return {'found': False, 'error': 'no_product'}
        currency = config.currency_id

        def with_taxes(amount):
            taxes = product.taxes_id.filtered(lambda t: t.company_id in config.company_id.parent_ids)
            if not taxes:
                return amount
            totals = taxes.compute_all(amount, currency, 1.0, product=product)
            return totals['total_included'] if config.iface_tax_included == 'total' else totals['total_excluded']

        price = with_taxes(config.pricelist_id._get_product_price(product, 1.0) if config.pricelist_id else product.lst_price)
        before = with_taxes(product.lst_price)
        discount = before > 0 and currency.compare_amounts(before, price) > 0 and (before - price) / before >= 0.005
        values = {
            'found': True,
            'name': product.display_name,
            'reference': product.default_code or '',
            'image': product.image_512.decode() if product.image_512 else '',
            'price': currency.round(price),
            'price_text': currency.format(currency.round(price)),
            'before_text': currency.format(currency.round(before)) if discount else '',
            'discount_text': f'-{round((before - price) / before * 100)} %' if discount else '',
            'months_text': '',
            'stock_text': '',
            'in_stock': None,
        }
        months = config._price_checker_months(product, price) if config.price_checker_show_months else 0
        if months > 1:
            values['months_text'] = _("Up to %(months)s months without interest of %(amount)s",
                                      months=months, amount=currency.format(currency.round(price / months)))
        if config.price_checker_show_stock and config._price_checker_tracks_stock(product):
            warehouse = config._price_checker_warehouse()
            available = product.with_context(warehouse_id=warehouse.id).free_qty if warehouse else product.free_qty
            values['in_stock'] = available > 0
            values['stock_text'] = _("Available in this store") if available > 0 else _("Out of stock in this store")
        return values

    def _price_checker_tracks_stock(self, product):
        """Whether Odoo counts the stock of this product (Inventory installed and the product is storable)."""
        if 'free_qty' not in product._fields:
            return False
        if 'is_storable' in product._fields:
            return product.is_storable
        return product.type == 'product'  # Odoo 17

    def _price_checker_warehouse(self):
        """The warehouse of this store: the one of its operation type."""
        self.ensure_one()
        if 'warehouse_id' in self._fields and self.warehouse_id:
            return self.warehouse_id
        if 'picking_type_id' in self._fields:
            return self.picking_type_id.warehouse_id
        return self.env['stock.warehouse'] if 'stock.warehouse' in self.env else None

    def _price_checker_months(self, product, price):
        """The most months without interest this product can be paid in at this store: 0 when nothing says.

        Reads the XPago payment rules when the XPago app is installed; other payment modules can override it."""
        self.ensure_one()
        if 'payment.xpago.rule' not in self.env:
            return 0
        Rule = self.env['payment.xpago.rule']
        line = {'product': product, 'unit_price': price, 'amount': price}
        try:
            terms = Rule.sudo()._xpago_plan(self.company_id, 'pos', [line], price, config=self)[0]['terms']
        except Exception:  # noqa: BLE001 — the rules never stop the price from showing
            return 0
        return max([t for t in terms or [] if t > 1], default=0)
