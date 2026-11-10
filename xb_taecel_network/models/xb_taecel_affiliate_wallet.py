# -*- coding: utf-8 -*-
import html

from odoo import api, fields, models

from odoo.addons.xb_pos_taecel.models.pos_compat import HAS_MODEL_CONSTRAINT


class XbTaecelAffiliateWallet(models.Model):
    """One bolsa of one affiliate.

    Same shape as the account's own wallet and for the same reason: TAECEL
    funds Tiempo Aire, Pago de Servicios and Timbres CFDI separately and does
    not let balance move between them, so a single "balance" per affiliate
    would be a fiction. A new bolsa from TAECEL is a row, not a migration.
    """
    _name = 'xb.taecel.affiliate.wallet'
    _description = 'TAECEL Affiliate Wallet'
    _order = 'bolsa_id'

    affiliate_id = fields.Many2one(
        'xb.taecel.affiliate', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='affiliate_id.company_id', store=True)
    currency_id = fields.Many2one(related='affiliate_id.currency_id')

    bolsa_id = fields.Char(required=True, help='TAECEL bolsa id (1/2/3).')
    name = fields.Char(required=True)
    balance = fields.Monetary(readonly=True)
    balance_date = fields.Datetime(readonly=True)

    if HAS_MODEL_CONSTRAINT:
        _bolsa_affiliate_uniq = models.Constraint(
            'unique(bolsa_id, affiliate_id)',
            "This wallet already exists for the affiliate.",
        )
    else:
        _sql_constraints = [
            ('bolsa_affiliate_uniq', 'unique(bolsa_id, affiliate_id)',
             "This wallet already exists for the affiliate."),
        ]

    def _clean_name(self, row):
        """Wallet name as TAECEL sends it, HTML entities and all.

        getBalance labels a bolsa 'Cr&eacute;ditos SMS'; unescaped it would be
        stored and displayed literally.
        """
        raw = row.get('Bolsa') or row.get('Nombre') or ''
        return html.unescape(str(raw)).strip()

    @api.depends('name', 'balance', 'currency_id')
    def _compute_display_name(self):
        for wallet in self:
            wallet.display_name = '%s: %s' % (
                wallet.name,
                wallet.currency_id.format(wallet.balance) if wallet.currency_id
                else wallet.balance)
