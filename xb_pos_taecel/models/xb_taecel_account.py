# -*- coding: utf-8 -*-
import html
import logging
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .. import const
from .pos_compat import HAS_MODEL_CONSTRAINT, pos_config_record
from .taecel_client import TaecelClient

_logger = logging.getLogger(__name__)


def _money(text):
    """TAECEL returns money as '$100,000,000.00'. Turn it into a float."""
    if text in (None, False, ''):
        return 0.0
    cleaned = re.sub(r'[^\d.-]', '', str(text))
    try:
        return float(cleaned or 0.0)
    except ValueError:
        return 0.0


class XbTaecelAccount(models.Model):
    _name = 'xb.taecel.account'
    _description = 'TAECEL Account'
    _inherit = ['pos.load.mixin']

    name = fields.Char(required=True, default='TAECEL')
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    shared_company_ids = fields.Many2many(
        'res.company', 'xb_taecel_account_shared_company_rel',
        'account_id', 'company_id', string='Also Used By',
        help='Other companies whose registers sell on this account. A group '
             'that funds one single TAECEL account lists them here; leave it '
             'empty to keep the account private to its own company.')
    currency_id = fields.Many2one(related='company_id.currency_id')
    active = fields.Boolean(default=True)

    # -- Credentials -------------------------------------------------------
    # Issued by TAECEL only after the "Levantamiento Tecnologico" is approved
    # and test transactions are verified. Never sent to the POS, and readable
    # only by Settings administrators: whoever holds these can spend the
    # wallets from outside Odoo, which is not a shop manager's business. The
    # groups are declared on the field, not just hidden in the view, so they
    # never reach the browser. Internal calls go through _get_client (sudo).
    api_key = fields.Char(string='API Key', groups='base.group_system')
    api_nip = fields.Char(string='API NIP', groups='base.group_system')
    test_mode = fields.Boolean(
        string='Test Mode', default=True,
        help='Use the TAECEL test endpoint and test product codes. Turn this '
             'off only once TAECEL has validated your test transactions and '
             'issued production credentials.')
    url_prod = fields.Char(string='Production URL', default=const.DEFAULT_URL_PROD)
    url_test = fields.Char(string='Test URL', default=const.DEFAULT_URL_TEST)
    timeout = fields.Integer(
        string='Timeout (s)', default=const.DEFAULT_TIMEOUT,
        help='How long the cashier waits for TAECEL before the sale is parked '
             'for automatic reconciliation. Keep it short.')

    # -- Catalog & wallets -------------------------------------------------
    wallet_ids = fields.One2many('xb.taecel.wallet', 'account_id')
    carrier_ids = fields.One2many('xb.taecel.carrier', 'account_id')
    product_ids = fields.One2many('xb.taecel.product', 'account_id')
    carrier_count = fields.Integer(compute='_compute_counts')
    product_count = fields.Integer(compute='_compute_counts')
    catalog_date = fields.Datetime(string='Catalog Synced', readonly=True, copy=False)

    state = fields.Selection([
        ('draft', 'Not Connected'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ], default='draft', copy=False)
    connection_msg = fields.Char(readonly=True, copy=False)

    # -- Commercial --------------------------------------------------------
    # TAECEL grants a commission to the account holder, and a distributor
    # re-grants a smaller one to each affiliate it registers in MI RED: the
    # distributor's profit is the difference. So the rate is a property of
    # *this* account, not a constant -- a distributor install and an affiliate
    # install of this module hold different numbers.
    role = fields.Selection([
        ('distributor', 'Distributor'),
        ('affiliate', 'Affiliate'),
    ], string='Account Type', default='distributor', required=True,
        help='Distributor: you contracted TAECEL directly and may register '
             'affiliates. Affiliate: a distributor registered you and funds '
             'your wallets, and sets the commission you earn.')
    taecel_uid = fields.Char(
        string='TAECEL Account ID',
        help='Account number TAECEL assigned you, as shown in the portal. '
             'A distributor looks its affiliates up by this number in MI RED.')
    commission_rate = fields.Float(
        string='My Commission (%)', default=6.5,
        help='Commission granted on THIS account, not the one you grant to '
             'others. A distributor starts at 6.5% and can request 6.95% '
             'with volume; an affiliate earns whatever its distributor '
             'assigned it in MI RED. Informational.')

    @api.onchange('role')
    def _onchange_role(self):
        """Keep the rate honest when the account type changes.

        6.5% is the distributor's own commission; leaving it on an affiliate
        account would overstate what that counter actually earns.
        """
        for account in self:
            if account.role == 'affiliate' and account.commission_rate == 6.5:
                account.commission_rate = 5.5  # market floor TAECEL suggests
            elif account.role == 'distributor' and account.commission_rate == 5.5:
                account.commission_rate = 6.5

    config_ids = fields.Many2many(
        'pos.config', string='Points of Sale',
        help='POS where this TAECEL account can be used. Leave empty for all.')

    # Odoo 19 dropped _sql_constraints in favour of models.Constraint;
    # Odoo 18 has no models.Constraint. Declaring the wrong one is a
    # silent no-op, so pick at import time (see pos_compat).
    if HAS_MODEL_CONSTRAINT:
        _company_uniq = models.Constraint(
            'unique(company_id)',
            "Only one TAECEL account per company.",
        )
    else:
        _sql_constraints = [
            ('company_uniq', 'unique(company_id)',
             "Only one TAECEL account per company."),
        ]

    @api.depends('carrier_ids', 'product_ids')
    def _compute_counts(self):
        for account in self:
            account.carrier_count = len(account.carrier_ids)
            account.product_count = len(account.product_ids)

    # -- Helpers -----------------------------------------------------------
    @property
    def base_url(self):
        self.ensure_one()
        return self.url_test if self.test_mode else self.url_prod

    def _get_client(self):
        self.ensure_one()
        account = self.sudo()
        if not (account.api_key and account.api_nip):
            raise UserError(_(
                'The TAECEL account has no credentials yet.\n\n'
                'They are issued once TAECEL approves your "Levantamiento '
                'Tecnologico" (cc@taecel.com) and validates your test '
                'transactions.'))
        return TaecelClient(
            account.base_url, account.api_key, account.api_nip, account.timeout)

    def _wallet(self, bolsa_id):
        """Return (creating if needed) the wallet record for a bolsa id."""
        self.ensure_one()
        wallet = self.wallet_ids.filtered(lambda w: w.bolsa_id == str(bolsa_id))
        if not wallet:
            wallet = self.env['xb.taecel.wallet'].create({
                'account_id': self.id,
                'bolsa_id': str(bolsa_id),
                'name': const.BOLSA_NAMES.get(str(bolsa_id), _('Wallet %s', bolsa_id)),
            })
        return wallet

    def wallet_balance(self, bolsa_id):
        self.ensure_one()
        wallet = self.wallet_ids.filtered(lambda w: w.bolsa_id == str(bolsa_id))
        return wallet.balance if wallet else 0.0

    # -- Catalog sync ------------------------------------------------------
    def action_sync_catalog(self):
        """Pull bolsas, carriers and products from getProducts in one pass."""
        self.ensure_one()
        result = self._get_client().get_products()
        if not result.ok:
            self.write({'state': 'error', 'connection_msg': result.message})
            raise UserError(_('Could not read the TAECEL catalog:\n\n%s', result.message))

        data = result.data or {}
        # Bolsas -> wallets (names come from TAECEL; balances filled by sales).
        for bolsa in data.get('bolsas') or []:
            self._wallet(str(bolsa.get('ID'))).name = bolsa.get('Nombre') or _('Wallet')
        # Carriers first, then products link to them by uid.
        carriers_by_uid = self.env['xb.taecel.carrier']._sync_from_taecel(
            self, data.get('carriers') or [])
        count = self.env['xb.taecel.product']._sync_from_taecel(
            self, data.get('productos') or [], carriers_by_uid)

        self.write({
            'state': 'connected',
            'connection_msg': _('Catalog synced.'),
            'catalog_date': fields.Datetime.now(),
        })
        return self._notify(_('TAECEL catalog'),
                            _('%(c)s carriers, %(p)s products synced.',
                              c=len(carriers_by_uid), p=count))

    def action_test_connection(self):
        """A successful getProducts is proof the credentials work."""
        self.ensure_one()
        result = self._get_client().get_products()
        if result.ok:
            self.write({'state': 'connected', 'connection_msg': _('Connection OK.')})
            return self._notify(_('TAECEL'), _('Connection OK.'))
        self.write({'state': 'error', 'connection_msg': result.message})
        raise UserError(_('TAECEL refused the connection:\n\n%s', result.message))

    # -- Balance via getBalance (CONFIRMED) --------------------------------
    def action_refresh_balance(self):
        """Refresh every wallet from a single getBalance call.

        Per TAECEL: getBalance does NOT take a bolsa -- one call returns a row
        per bolsa (Tiempo Aire, Pago de Servicios, Timbres CFDI, Creditos SMS).
        We map each row onto its wallet by bolsa id. This is the accurate,
        direct balance; the getSales pull below is kept only to reconcile
        pending transactions, not to read balances.
        """
        for account in self:
            result = account._get_client().get_balance()
            if not result.ok:
                account.connection_msg = result.message
                continue
            for row in result.data or []:
                bolsa_id = str(row.get(const.K_BAL_BOLSA_ID) or '').strip()
                if not bolsa_id:
                    continue
                wallet = account._wallet(bolsa_id)
                vals = {
                    'balance': _money(row.get(const.K_BAL_SALDO)),
                    'balance_date': fields.Datetime.now(),
                }
                name = row.get('Bolsa')
                if name:
                    # TAECEL sends names HTML-escaped, e.g. 'Cr&eacute;ditos SMS'.
                    vals['name'] = html.unescape(name)
                wallet.write(vals)
        return True

    # -- Reconciliation via getSales ---------------------------------------
    # Settles transactions whose outcome we still do not hold, by matching them
    # in getSales. Balances now come from getBalance (above); this pull is for
    # reconciliation only.
    def action_refresh_from_sales(self):
        for account in self:
            client = account._get_client()
            today = fields.Date.context_today(account).strftime('%Y-%m-%d')
            for bolsa_id in account.wallet_ids.mapped('bolsa_id') or [
                    const.BOLSA_AIRTIME, const.BOLSA_SERVICES]:
                result = client.get_sales(today, bolsa_id)
                if not result.ok:
                    account.connection_msg = result.message
                    continue
                account._apply_sales(bolsa_id, result.data or [])
        return True

    def _apply_sales(self, bolsa_id, sales):
        """Update the wallet balance and settle matching transactions.

        ``sales`` is newest-first (as TAECEL returns it); the first row's
        "Saldo Final" is the current wallet balance.
        """
        self.ensure_one()
        if not isinstance(sales, list) or not sales:
            return
        wallet = self._wallet(bolsa_id)
        wallet.write({
            'balance': _money(sales[0].get(const.K_SALE_FINAL_BALANCE)),
            'balance_date': fields.Datetime.now(),
        })
        # Settle any of our transactions that TAECEL now reports on.
        Txn = self.env['xb.taecel.transaction']
        for sale in sales:
            trans_id = sale.get(const.K_SALE_TRANS_ID)
            if not trans_id:
                continue
            txn = Txn.search([
                ('account_id', '=', self.id), ('trans_id', '=', str(trans_id)),
                ('state', 'in', [const.STATE_SENT, const.STATE_TIMEOUT]),
            ], limit=1)
            if txn:
                txn._settle_from_sale(sale)

    # -- POS ---------------------------------------------------------------
    @api.model
    def _serving_domain(self, pos_config=None, company=None):
        """Accounts a given register may sell on.

        The single source of truth for "who may use this account", shared by
        the POS loader and by ``pos.order._xb_taecel_account``. Keeping one
        definition is not tidiness: when the front end offered an account the
        back end then refused, the register took the customer's money and never
        dispatched the recharge.
        """
        domain = [('active', '=', True)]
        if pos_config:
            domain += ['|', ('config_ids', '=', False),
                       ('config_ids', 'in', pos_config.ids)]
        company = company or (pos_config.company_id if pos_config else None)
        if company:
            domain += ['|', ('company_id', 'in', company.ids),
                       ('shared_company_ids', 'in', company.ids)]
        return domain

    @api.model
    def _load_pos_data_domain(self, data, config=None):
        return self._serving_domain(pos_config_record(self.env, config))

    @api.model
    def _load_pos_data_fields(self, config=None):
        # Credentials are deliberately absent: the POS never sees them; every
        # call to TAECEL is made server-side.
        return ['id', 'name', 'test_mode', 'currency_id']

    # -- Misc --------------------------------------------------------------
    def _notify(self, title, message, kind='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': kind},
        }

    def action_view_products(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('TAECEL Catalog'),
            'res_model': 'xb.taecel.product',
            'view_mode': 'list,form',
            'domain': [('account_id', '=', self.id)],
        }

    # -- Cron --------------------------------------------------------------
    @api.model
    def _cron_refresh_balance(self):
        self.search([('active', '=', True)]).action_refresh_balance()
