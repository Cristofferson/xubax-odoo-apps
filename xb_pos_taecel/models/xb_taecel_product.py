# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _

from .pos_compat import HAS_MODEL_CONSTRAINT

from .. import const

_logger = logging.getLogger(__name__)


class XbTaecelProduct(models.Model):
    """Local mirror of the TAECEL catalog (the fixed-amount ``productos``).

    A cache, not a source of truth: TAECEL adds and retires products without
    notice, so the catalog is re-synced rather than maintained by hand. Records
    are deactivated instead of deleted, because transactions point at them.

    Free-amount carriers have no products here -- their amount is typed at the
    till; only catalog carriers list fixed amounts.
    """
    _name = 'xb.taecel.product'
    _description = 'TAECEL Product'
    _order = 'carrier_id, amount'
    _inherit = ['pos.load.mixin']

    account_id = fields.Many2one(
        'xb.taecel.account', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='account_id.company_id', store=True)
    currency_id = fields.Many2one(related='account_id.currency_id')

    carrier_id = fields.Many2one('xb.taecel.carrier', ondelete='cascade', index=True)
    code = fields.Char(required=True, index=True,
                       help='Product code TAECEL expects to dispatch, e.g. TEL050.')
    name = fields.Char()
    carrier_name = fields.Char(help='Carrier name as it came from TAECEL.')
    bolsa_id = fields.Char(help='Wallet this product is charged against.')
    category = fields.Char()
    amount = fields.Monetary(help='Fixed sale amount for this product.')
    description = fields.Text(help='Promo/plan detail, shown to the cashier.')
    validity = fields.Char(string='Vigencia')
    taecel_pro_id = fields.Char(string='TAECEL proID')
    subscription = fields.Boolean()
    active = fields.Boolean(default=True)

    # Odoo 19 dropped _sql_constraints in favour of models.Constraint;
    # Odoo 18 has no models.Constraint. Declaring the wrong one is a
    # silent no-op, so pick at import time (see pos_compat).
    if HAS_MODEL_CONSTRAINT:
        _code_account_uniq = models.Constraint(
            'unique(code, account_id)',
            "This TAECEL product code already exists for this account.",
        )
    else:
        _sql_constraints = [
            ('code_account_uniq', 'unique(code, account_id)',
             "This TAECEL product code already exists for this account."),
        ]

    @api.depends('name', 'carrier_name', 'amount', 'currency_id')
    def _compute_display_name(self):
        for product in self:
            money = (product.currency_id.format(product.amount)
                     if product.currency_id and product.amount else '')
            bits = [b for b in (product.carrier_name, money, product.name) if b]
            product.display_name = ' '.join(bits) or product.code

    # -- Sync --------------------------------------------------------------
    @api.model
    def _sync_from_taecel(self, account, products, carriers_by_uid):
        """Reconcile the mirror with a getProducts ``data.productos`` list.

        ``carriers_by_uid`` comes from the carrier sync run just before. Returns
        the number of products seen; anything absent is archived, not dropped.
        """
        seen_codes = []
        for row in products or []:
            values = self._values_from_payload(account, row, carriers_by_uid)
            if not values:
                continue
            seen_codes.append(values['code'])
            existing = self.with_context(active_test=False).search([
                ('account_id', '=', account.id), ('code', '=', values['code']),
            ], limit=1)
            if existing:
                existing.write(dict(values, active=True))
            else:
                self.create(values)

        if seen_codes:
            stale = self.search([
                ('account_id', '=', account.id), ('code', 'not in', seen_codes),
            ])
            stale.write({'active': False})
        return len(seen_codes)

    @api.model
    def _values_from_payload(self, account, row, carriers_by_uid):
        code = str(row.get(const.K_PROD_CODE) or '').strip()
        if not code:
            return None
        try:
            amount = float(row.get(const.K_PROD_AMOUNT) or 0.0)
        except (TypeError, ValueError):
            amount = 0.0
        carrier = carriers_by_uid.get(str(row.get(const.K_PROD_CARRIER_ID) or ''))
        return {
            'account_id': account.id,
            'carrier_id': carrier.id if carrier else False,
            'code': code,
            'name': row.get(const.K_PROD_NAME) or '',
            'carrier_name': row.get(const.K_PROD_CARRIER) or '',
            'bolsa_id': str(row.get(const.K_PROD_BOLSA) or ''),
            'category': row.get(const.K_PROD_CATEG) or '',
            'amount': amount,
            'description': row.get(const.K_PROD_DESC) or '',
            'validity': row.get(const.K_PROD_VIGENCIA) or '',
            'taecel_pro_id': str(row.get(const.K_PROD_ID) or ''),
            'subscription': str(row.get(const.K_PROD_SUBSCRIPTION) or '0') == '1',
        }

    # -- POS ---------------------------------------------------------------
    @api.model
    def _load_pos_data_domain(self, data, config=None):
        return [('active', '=', True)]

    @api.model
    def _load_pos_data_fields(self, config=None):
        return ['id', 'code', 'name', 'carrier_id', 'carrier_name', 'bolsa_id',
                'category', 'amount', 'description', 'validity', 'account_id']
