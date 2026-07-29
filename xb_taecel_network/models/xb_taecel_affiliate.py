# -*- coding: utf-8 -*-
"""One affiliate of a TAECEL distributor network.

Why this model exists at all: TAECEL's web service has **no** network method.
There is no "list my affiliates", no "read affiliate X's balance", no transfer
and no suspension -- MI RED is a portal, and the API only ever answers for the
account whose credentials signed the request.

So the network view is assembled here, from the one thing the API does give us:
every affiliate holds its own ws key/nip (TAECEL issues them when the
distributor registers it), and with those we can ask that affiliate's own
getBalance / getSales / urlReporteCompra. One record per affiliate, one set of
credentials, and the distributor gets the picture the portal will not give it.

Consequence worth stating out loud: this model stores someone else's
credentials. They are held exactly like the account's own -- readable only by
Settings administrators, never rendered into a client payload -- because
whoever holds them can spend that affiliate's balance from outside Odoo.
"""
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.xb_pos_taecel import const
from odoo.addons.xb_pos_taecel.models.pos_compat import HAS_MODEL_CONSTRAINT
from odoo.addons.xb_pos_taecel.models.taecel_client import TaecelClient
from odoo.addons.xb_pos_taecel.models.xb_taecel_account import _money

_logger = logging.getLogger(__name__)


class XbTaecelAffiliate(models.Model):
    _name = 'xb.taecel.affiliate'
    _description = 'TAECEL Affiliate'
    _order = 'name'

    name = fields.Char(required=True, help='Trade name of the point of sale.')
    # Not required on purpose: TAECEL hands the account number over on its own
    # schedule, and the panel never needs it -- balances and sales are pulled
    # with the affiliate's own credentials. Demanding it up front would block
    # registering an affiliate that is already selling.
    taecel_uid = fields.Char(
        string='TAECEL Account ID',
        help='Account number TAECEL assigned to this affiliate, as shown in '
             'MI RED. This is what you search by in the portal. Leave it empty '
             'until TAECEL gives it to you.')
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one(
        'res.partner', string='Contact',
        help='Optional: who runs this point of sale, for your own records.')
    note = fields.Text(string='Notes')

    # The distributor account this affiliate hangs from. It supplies the
    # company (so the record obeys the same multi-company rules as the rest of
    # the module) and the commission the margin is measured against.
    account_id = fields.Many2one(
        'xb.taecel.account', string='Distributor Account', required=True,
        ondelete='cascade', index=True,
        default=lambda self: self.env['xb.taecel.account'].search(
            [('role', '=', 'distributor')], limit=1),
        help='Your own TAECEL account, the one that registered this affiliate.')
    company_id = fields.Many2one(related='account_id.company_id', store=True)
    currency_id = fields.Many2one(related='account_id.currency_id')

    # -- Credentials -------------------------------------------------------
    # The affiliate's OWN ws credentials, not the distributor's. Sharing the
    # distributor's would make the affiliate spend the distributor's wallet
    # and leave nothing to reconcile per affiliate -- and no margin at all.
    api_key = fields.Char(string='API Key', groups='base.group_system')
    api_nip = fields.Char(string='API NIP', groups='base.group_system')

    state = fields.Selection([
        ('draft', 'Not Connected'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ], default='draft', copy=False)
    connection_msg = fields.Char(readonly=True, copy=False)

    # -- Commercial --------------------------------------------------------
    commission_rate = fields.Float(
        string='Their Commission (%)', default=5.5,
        help='Commission you granted this affiliate in MI RED. TAECEL '
             'suggests 5.5% as the market floor.')
    my_commission_rate = fields.Float(
        related='account_id.commission_rate', string='My Commission (%)')
    margin_rate = fields.Float(
        string='My Margin (%)', compute='_compute_margin_rate', store=True,
        help='The spread you keep: your commission minus theirs. This is '
             'where a distributor earns.')

    # -- Funding -----------------------------------------------------------
    deposit_reference = fields.Char(
        string='Deposit Reference', readonly=True, copy=False,
        help='Bank reference THIS affiliate deposits against. A deposit '
             'quoting it is credited to the affiliate automatically, so no '
             'balance transfer from you is needed.')
    deposit_url = fields.Char(string='Report a Deposit', readonly=True, copy=False)
    deposit_date = fields.Datetime(string='Reference Read', readonly=True, copy=False)

    # -- Balances & sales --------------------------------------------------
    wallet_ids = fields.One2many('xb.taecel.affiliate.wallet', 'affiliate_id')
    sale_ids = fields.One2many('xb.taecel.affiliate.sale', 'affiliate_id')
    balance_total = fields.Monetary(
        compute='_compute_balance_total', store=True, string='Total Balance')
    balance_date = fields.Datetime(readonly=True, copy=False)
    sales_count = fields.Integer(compute='_compute_sales', string='Sales')
    sales_volume = fields.Monetary(compute='_compute_sales', string='Volume')
    my_margin = fields.Monetary(compute='_compute_sales', string='My Margin')

    # The pair stays unique, but only for affiliates whose number is known: an
    # empty string counts as a value for a UNIQUE index, so two affiliates
    # still waiting on their number would collide. Postgres keeps NULLs
    # distinct, so blanks are normalised to NULL on the way in.
    if HAS_MODEL_CONSTRAINT:
        _uid_account_uniq = models.Constraint(
            'unique(taecel_uid, account_id)',
            "This affiliate is already registered under that account.",
        )
    else:
        _sql_constraints = [
            ('uid_account_uniq', 'unique(taecel_uid, account_id)',
             "This affiliate is already registered under that account."),
        ]

    @api.model
    def _clean_uid(self, vals):
        """Blank or padded account numbers are never a real number.

        A stray space would also defeat the lookup in MI RED, which is the
        whole point of storing it.
        """
        if 'taecel_uid' in vals:
            vals['taecel_uid'] = (vals['taecel_uid'] or '').strip() or False
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._clean_uid(vals) for vals in vals_list])

    def write(self, vals):
        return super().write(self._clean_uid(vals))

    @api.depends('commission_rate', 'account_id.commission_rate')
    def _compute_margin_rate(self):
        for affiliate in self:
            affiliate.margin_rate = (
                affiliate.account_id.commission_rate - affiliate.commission_rate)

    @api.depends('wallet_ids.balance')
    def _compute_balance_total(self):
        for affiliate in self:
            affiliate.balance_total = sum(affiliate.wallet_ids.mapped('balance'))

    @api.depends('sale_ids.amount', 'sale_ids.status', 'margin_rate')
    def _compute_sales(self):
        """Volume and margin over the sales pulled so far.

        Only successful sales count: a failed recharge is refunded by TAECEL,
        so it moves no volume and earns no spread.
        """
        for affiliate in self:
            done = affiliate.sale_ids.filtered(lambda s: s.status == 'ok')
            volume = sum(done.mapped('amount'))
            affiliate.sales_count = len(done)
            affiliate.sales_volume = volume
            affiliate.my_margin = volume * affiliate.margin_rate / 100.0

    @api.constrains('commission_rate', 'account_id')
    def _check_commission(self):
        """A commission above the distributor's own is a loss on every sale."""
        for affiliate in self:
            if affiliate.commission_rate > affiliate.account_id.commission_rate:
                raise UserError(_(
                    'You granted %(theirs).2f%% to %(name)s but TAECEL grants '
                    'you %(mine).2f%%. Every sale would cost you the '
                    'difference.',
                    theirs=affiliate.commission_rate, name=affiliate.name,
                    mine=affiliate.account_id.commission_rate))

    # -- Transport ---------------------------------------------------------
    def _get_client(self):
        """A client signed with THIS affiliate's credentials."""
        self.ensure_one()
        affiliate = self.sudo()
        if not (affiliate.api_key and affiliate.api_nip):
            raise UserError(_(
                'No credentials for %s yet.\n\n'
                'TAECEL issues its own ws key and NIP to each affiliate when '
                'you register it in MI RED; they are mailed to the address on '
                'the account. Ask for them as a PDF: the portal truncates the '
                'key on screen and a copied key is rejected with a 403.',
                affiliate.name))
        return TaecelClient(
            affiliate.account_id.base_url,
            affiliate.api_key, affiliate.api_nip,
            affiliate.account_id.timeout)

    def _wallet(self, bolsa_id):
        self.ensure_one()
        wallet = self.wallet_ids.filtered(lambda w: w.bolsa_id == str(bolsa_id))
        if not wallet:
            wallet = self.env['xb.taecel.affiliate.wallet'].create({
                'affiliate_id': self.id,
                'bolsa_id': str(bolsa_id),
                'name': const.BOLSA_NAMES.get(str(bolsa_id), _('Wallet %s', bolsa_id)),
            })
        return wallet

    # -- Actions -----------------------------------------------------------
    def action_test_connection(self):
        """getBalance is proof enough that the affiliate's credentials work."""
        self.ensure_one()
        result = self._get_client().get_balance()
        if result.ok:
            self.write({'state': 'connected', 'connection_msg': _('Connection OK.')})
            return self._notify(_('TAECEL'), _('Connection OK.'))
        self.write({'state': 'error', 'connection_msg': result.message})
        raise UserError(_('TAECEL refused the connection:\n\n%s', result.message))

    def action_refresh_balance(self):
        """One getBalance per affiliate returns every bolsa it holds."""
        for affiliate in self:
            result = affiliate._get_client().get_balance()
            if not result.ok:
                affiliate.write({'state': 'error', 'connection_msg': result.message})
                continue
            for row in result.data or []:
                bolsa_id = str(row.get(const.K_BAL_BOLSA_ID) or '').strip()
                if not bolsa_id:
                    continue
                wallet = affiliate._wallet(bolsa_id)
                wallet.write({
                    'name': wallet._clean_name(row) or wallet.name,
                    'balance': _money(row.get(const.K_BAL_SALDO)),
                    'balance_date': fields.Datetime.now(),
                })
            affiliate.write({
                'state': 'connected',
                'connection_msg': _('Balances refreshed.'),
                'balance_date': fields.Datetime.now(),
            })
        return True

    def action_fetch_deposit_reference(self):
        """The reference this affiliate funds itself with.

        Handing it over is what makes a distributor stop transferring balance
        by hand: a referenced deposit is credited automatically, while a
        transfer is portal-only and rejected 30 minutes after it is raised
        unless TAECEL is e-mailed at that very moment.
        """
        self.ensure_one()
        result = self._get_client().get_deposit_reference()
        if not result.ok:
            raise UserError(_('Could not read the deposit reference:\n\n%s',
                              result.message))
        self.write({
            'deposit_reference': result.data.get(const.K_REPORT_REF),
            'deposit_url': result.data.get(const.K_REPORT_URL),
            'deposit_date': fields.Datetime.now(),
        })
        return self._notify(
            _('Deposit reference'),
            _('%(name)s funds itself with reference %(ref)s.',
              name=self.name, ref=self.deposit_reference))

    def action_pull_sales(self, day=None):
        """Pull one day of sales, per wallet, for each affiliate.

        getSales takes a bolsa, so it is one call per wallet the affiliate
        holds. Rows are keyed by TransID, which makes the pull idempotent:
        running it twice, or re-running it for a day already fetched, updates
        instead of duplicating.
        """
        Sale = self.env['xb.taecel.affiliate.sale']
        fecha = day or fields.Date.context_today(self).strftime('%Y-%m-%d')
        pulled = 0
        for affiliate in self:
            client = affiliate._get_client()
            wallets = affiliate.wallet_ids or affiliate._wallet(const.BOLSA_AIRTIME)
            for wallet in wallets:
                result = client.get_sales(fecha, wallet.bolsa_id)
                if not result.ok:
                    # A wallet the affiliate does not hold answers with an
                    # error; that is not a failure of the pull.
                    _logger.info('TAECEL getSales %s/%s: %s',
                                 affiliate.name, wallet.bolsa_id, result.message)
                    continue
                pulled += Sale._absorb(affiliate, wallet.bolsa_id, result.data or [])
        return self._notify(_('TAECEL network'),
                            _('%(n)s sales pulled for %(d)s.', n=pulled, d=fecha))

    def action_view_sales(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales'),
            'res_model': 'xb.taecel.affiliate.sale',
            'view_mode': 'list,form',
            'domain': [('affiliate_id', '=', self.id)],
            'context': {'default_affiliate_id': self.id},
        }

    # -- Scheduled ---------------------------------------------------------
    @api.model
    def _cron_refresh_network(self):
        """Keep balances and today's sales current, affiliate by affiliate.

        Isolated per affiliate on purpose: one affiliate with stale
        credentials must not stop the others from being read, and one commit
        each means a network of twenty does not lose everything to the last
        one failing.
        """
        for affiliate in self.search([]):
            try:
                affiliate.action_refresh_balance()
                affiliate.action_pull_sales()
                self.env.cr.commit()
            except Exception as err:          # noqa: BLE001 -- cron must go on
                self.env.cr.rollback()
                _logger.warning('TAECEL network: %s failed: %s',
                                affiliate.name, err)

    def _notify(self, title, message, kind='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': kind},
        }
