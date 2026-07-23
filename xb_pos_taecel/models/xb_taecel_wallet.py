# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .pos_compat import HAS_MODEL_CONSTRAINT

from .. import const


class XbTaecelWallet(models.Model):
    """One TAECEL "bolsa" (wallet) of an account.

    A record per bolsa rather than fixed columns on the account: TAECEL funds
    Tiempo Aire, Pago de Servicios and Timbres CFDI through separate bank
    accounts and does not let balance move between them, so each is tracked and
    overdraw-guarded on its own. Modelling them as rows also means a new bolsa
    from TAECEL is data, not a migration.
    """
    _name = 'xb.taecel.wallet'
    _description = 'TAECEL Wallet'
    _order = 'bolsa_id'
    _inherit = ['pos.load.mixin']

    account_id = fields.Many2one(
        'xb.taecel.account', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='account_id.company_id', store=True)
    currency_id = fields.Many2one(related='account_id.currency_id')

    bolsa_id = fields.Char(required=True, help='TAECEL bolsa id (1/2/3).')
    name = fields.Char(required=True)
    balance = fields.Monetary(readonly=True)
    balance_date = fields.Datetime(readonly=True)
    low_threshold = fields.Monetary(
        string='Low-balance Warning', default=500.0,
        help='Warn the cashier in the POS when this wallet drops below it.')

    # Odoo 19 dropped _sql_constraints in favour of models.Constraint;
    # Odoo 18 has no models.Constraint. Declaring the wrong one is a
    # silent no-op, so pick at import time (see pos_compat).
    if HAS_MODEL_CONSTRAINT:
        _bolsa_account_uniq = models.Constraint(
            'unique(bolsa_id, account_id)',
            "This wallet already exists for the account.",
        )
    else:
        _sql_constraints = [
            ('bolsa_account_uniq', 'unique(bolsa_id, account_id)',
             "This wallet already exists for the account."),
        ]

    @api.depends('name', 'balance', 'currency_id')
    def _compute_display_name(self):
        for wallet in self:
            wallet.display_name = '%s: %s' % (
                wallet.name,
                wallet.currency_id.format(wallet.balance) if wallet.currency_id
                else wallet.balance)

    @api.model
    def _load_pos_data_domain(self, data, config=None):
        return [('account_id.active', '=', True)]

    @api.model
    def _load_pos_data_fields(self, config=None):
        return ['id', 'account_id', 'bolsa_id', 'name', 'balance',
                'low_threshold', 'currency_id']
