from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.xpago import const


def parse_terms(text):
    """Months written as "3, 6, 12" -> [3, 6, 12]. Raises ValueError on anything else."""
    terms = set()
    for part in (text or '').replace(';', ',').split(','):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit() or not 2 <= int(part) <= const.MAX_TERMS:
            raise ValueError(part)
        terms.add(int(part))
    return sorted(terms)


class PaymentXpagoRule(models.Model):
    """Which months without interest a sale may be paid in, and which account its money is deposited in, by what is
    sold: the amount of the sale, the price of each product (after its pricelist), the product or variant, its
    category and its tags. Like the promotions of Odoo: the rules are tried in order and the first that fits a
    product decides for it.

    The point of sale app adds where the rule applies at the register and the kiosk."""

    _name = 'payment.xpago.rule'
    _description = "XPago payment rule"
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10, help="Order of the rules: the first one that fits a product decides.")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')

    # Where and when
    use_online = fields.Boolean(string="Online", default=True,
                                help="Online store, payment links of orders and invoices.")
    date_from = fields.Date(string="From")
    date_to = fields.Date(string="Until")

    # The sale
    amount_min = fields.Monetary(string="Sale from", help="Total of the sale, taxes included. Empty: any.")
    amount_max = fields.Monetary(string="Sale up to")

    # The products
    product_tmpl_ids = fields.Many2many('product.template', string="Products")
    product_ids = fields.Many2many('product.product', string="Variants",
                                   help="Only these variants (for example, the ring in white gold).")
    categ_ids = fields.Many2many('product.category', string="Categories", help="Their subcategories too.")
    tag_ids = fields.Many2many('product.tag', string="Tags", help="Products with any of these tags.")
    price_min = fields.Monetary(string="Product price from",
                                help="Unit price in the sale, after its pricelist and discount, taxes included.")
    price_max = fields.Monetary(string="Product price up to")
    product_count = fields.Integer(compute='_compute_product_count', string="Products that fit")

    # What it decides
    msi_mode = fields.Selection([
        ('keep', "Does not change the months"),
        ('none', "Single payment only"),
        ('terms', "These months"),
    ], string="Months without interest", default='keep', required=True)
    terms = fields.Char(string="Months offered", help="For example \"3, 6, 12\".")
    bank_account_id = fields.Many2one(
        'payment.xpago.bank.account', string="Deposit account",
        domain="[('provider_id.company_id', 'parent_of', company_id)]",
        help="Where the money of these products is deposited. Empty: does not change the account.")

    @api.constrains('terms', 'msi_mode')
    def _check_terms(self):
        for rule in self.filtered(lambda r: r.msi_mode == 'terms'):
            try:
                if not parse_terms(rule.terms):
                    raise ValueError
            except ValueError:
                raise ValidationError(_(
                    "Write the months as whole numbers from 2 to %(max)s separated by commas, for example \"3, 6, 12\".",
                    max=const.MAX_TERMS)) from None

    @api.constrains('msi_mode', 'bank_account_id')
    def _check_effect(self):
        for rule in self:
            if rule.msi_mode == 'keep' and not rule.bank_account_id:
                raise ValidationError(_("The rule \"%s\" changes nothing: choose its months or its deposit account.", rule.name))

    @api.depends('product_tmpl_ids', 'product_ids', 'categ_ids', 'tag_ids')
    def _compute_product_count(self):
        Product = self.env['product.product']
        for rule in self:
            rule.product_count = Product.search_count(rule._product_domain()) if rule._has_product_filter() else 0

    def _has_product_filter(self):
        return bool(self.product_tmpl_ids or self.product_ids or self.categ_ids or self.tag_ids)

    def _product_domain(self):
        """The products this rule names, as a domain (the price is checked on each sale)."""
        domain = []
        if self.product_tmpl_ids:
            domain.append(('product_tmpl_id', 'in', self.product_tmpl_ids.ids))
        if self.product_ids:
            domain.append(('id', 'in', self.product_ids.ids))
        if self.categ_ids:
            domain.append(('categ_id', 'child_of', self.categ_ids.ids))
        if self.tag_ids:
            domain += ['|', ('product_tag_ids', 'in', self.tag_ids.ids), ('additional_product_tag_ids', 'in', self.tag_ids.ids)]
        return domain

    def _terms(self):
        """None: does not change the months; [1]: single payment only; else the months offered."""
        if self.msi_mode == 'none':
            return [1]
        if self.msi_mode == 'terms':
            return [1, *parse_terms(self.terms)]  # paying at once is always possible
        return None

    # === THE PLAN OF A SALE === #

    @api.model
    def _xpago_plan(self, company, channel, lines, total, config=None, date=None, split=False):
        """How a sale is charged: one part, or one per account and months when ``split``.

        ``channel``: 'online', or 'pos' / 'kiosk' with the point of sale app. ``lines``: dicts with ``product``
        (product.product), ``unit_price`` and ``amount`` (taxes included). Returns a list of dicts: ``amount``,
        ``account`` (payment.xpago.bank.account, may be empty), ``terms`` (None = the rules do not limit the months,
        [1] = single payment) and ``rules`` (the rules applied).
        """
        date = date or fields.Date.context_today(self)
        Account = self.env['payment.xpago.bank.account']
        # Only what is sold decides: a free line (shipping at $0, a gift) would otherwise fit every "price up to" rule
        # and take the months of the whole sale away. Its amount still counts in the total.
        lines = [line for line in lines if not self._xpago_skip_line(line, config)]
        rules = self.sudo().search([('company_id', 'parent_of', company.id)]).filtered(
            lambda r: r._xpago_fits_sale(channel, config, total, date))
        candidates = {}
        if rules and lines:
            ids = [line['product'].id for line in lines if line.get('product')]
            for rule in rules.filtered(lambda r: r._has_product_filter()):
                candidates[rule.id] = set(self.env['product.product'].sudo().with_context(active_test=False).search(
                    [('id', 'in', ids)] + rule._product_domain()).ids)
        decided = []
        for line in lines:
            fitting = rules.filtered(lambda r: r._xpago_fits_line(line, candidates))
            account_rule = fitting.filtered('bank_account_id')[:1]
            terms_rule = fitting.filtered(lambda r: r.msi_mode != 'keep')[:1]
            decided.append({
                'line': line,
                'account': account_rule.bank_account_id,
                'account_rule': account_rule,
                'terms': terms_rule._terms() if terms_rule else None,
                'terms_rule': terms_rule,
            })
        if not decided:
            return [{'amount': total, 'account': Account, 'terms': None, 'rules': self.browse()}]

        def merge(items, amount):
            terms = None
            for item in items:
                if item['terms'] is not None:
                    terms = item['terms'] if terms is None else [t for t in terms if t in item['terms']]
            if terms is not None and not terms:
                terms = [1]
            with_account = [item for item in items if item['account']]
            account = min(with_account, key=lambda i: (i['account_rule'].sequence, i['account_rule'].id))['account'] \
                if with_account else Account
            used = self.browse()
            for item in items:
                used |= item['account_rule'] | item['terms_rule']
            return {'amount': amount, 'account': account, 'terms': terms, 'rules': used}

        if not split:
            return [merge(decided, total)]
        groups = {}
        for item in decided:
            key = (item['account'].id, tuple(item['terms']) if item['terms'] is not None else None)
            groups.setdefault(key, []).append(item)
        if len(groups) == 1:
            return [merge(decided, total)]
        currency = company.currency_id
        parts = [merge(items, sum(i['line']['amount'] for i in items)) for items in groups.values()]
        # Discounts on the whole order, tips or rounding go with the largest part.
        rest = currency.round(total - sum(p['amount'] for p in parts))
        max(parts, key=lambda p: p['amount'])['amount'] += rest
        parts = [p for p in parts if currency.compare_amounts(p['amount'], 0) > 0]
        for part in parts:
            part['amount'] = currency.round(part['amount'])
        return parts

    @api.model
    def _xpago_skip_line(self, line, config):
        """Lines that are not products sold and must not decide the months or the account. The point of sale app
        adds its tips."""
        return not line.get('product') or self.env.company.currency_id.is_zero(line.get('amount') or 0.0)

    def _xpago_fits_channel(self, channel, config):
        """Whether the rule applies where the sale is made. The point of sale app adds the register and kiosk."""
        self.ensure_one()
        return channel == 'online' and self.use_online

    def _xpago_fits_sale(self, channel, config, total, date):
        self.ensure_one()
        if not self._xpago_fits_channel(channel, config):
            return False
        if (self.date_from and date < self.date_from) or (self.date_to and date > self.date_to):
            return False
        currency = self.currency_id
        if self.amount_min and currency.compare_amounts(total, self.amount_min) < 0:
            return False
        if self.amount_max and currency.compare_amounts(total, self.amount_max) > 0:
            return False
        return True

    def _xpago_fits_line(self, line, candidates):
        self.ensure_one()
        product = line.get('product')
        if self._has_product_filter() and (not product or product.id not in candidates.get(self.id, ())):
            return False
        currency = self.currency_id
        price = line.get('unit_price') or 0.0
        if self.price_min and currency.compare_amounts(price, self.price_min) < 0:
            return False
        if self.price_max and currency.compare_amounts(price, self.price_max) > 0:
            return False
        return True

    @api.model
    def _xpago_lines_from_records(self, records):
        """Plan lines from sale order lines, invoice lines or point of sale order lines."""
        lines = []
        for record in records:
            if record._name == 'sale.order.line':
                # Shipping is not a product sold: it is charged with the rest of the sale.
                if record.display_type or ('is_delivery' in record._fields and record.is_delivery):
                    continue
                qty, amount = record.product_uom_qty, record.price_total
            elif record._name == 'account.move.line':
                if record.display_type != 'product':
                    continue
                qty, amount = record.quantity, record.price_total
            elif record._name == 'pos.order.line':
                qty, amount = record.qty, record.price_subtotal_incl
            else:
                continue
            if not qty:
                continue
            lines.append({'product': record.product_id, 'unit_price': amount / qty, 'amount': amount})
        return lines

    def action_open_products(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Products of %s", self.name),
            'res_model': 'product.product',
            'view_mode': 'tree,form',
            'domain': self._product_domain(),
        }
