# -*- coding: utf-8 -*-
import logging
import time

from odoo import api, fields, models, _

from .. import const
from .xb_taecel_account import _money

_logger = logging.getLogger(__name__)


class XbTaecelTransaction(models.Model):
    """One dispatch attempt against TAECEL. Append-only by intent.

    The rule that shapes this model: **a transaction is never re-sent, only
    re-queried.** TAECEL dispatches real money to a real phone, and there is no
    refund. So a request that times out is not a failure to retry -- it is an
    unknown outcome to resolve, today by matching it in ``getSales``.

    Dispatch (``action_dispatch``) depends on the transactional API that is not
    yet documented; it is present but not reachable from the POS. Everything
    that settles a transaction already works against the confirmed getSales.
    """
    _name = 'xb.taecel.transaction'
    _description = 'TAECEL Transaction'
    _order = 'create_date desc, id desc'
    _inherit = ['pos.load.mixin']

    account_id = fields.Many2one('xb.taecel.account', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='account_id.company_id', store=True)
    currency_id = fields.Many2one(related='account_id.currency_id')

    product_id = fields.Many2one('xb.taecel.product', ondelete='restrict')
    carrier_id = fields.Many2one('xb.taecel.carrier', ondelete='restrict')
    bolsa_id = fields.Char(help='Wallet charged for this transaction.')
    product_code = fields.Char(help='TAECEL product code sent to dispatch.')

    reference = fields.Char(
        required=True,
        help='Phone number for airtime and PINs, or the bill reference for '
             'service payments.')
    amount = fields.Monetary(required=True)
    customer_fee = fields.Monetary(
        string='Customer Service Fee',
        help='Fee charged to the customer on top of the amount, as configured '
             'in the TAECEL platform. Must appear on the receipt.')
    total_charged = fields.Monetary(compute='_compute_total_charged', store=True)

    state = fields.Selection([
        (const.STATE_DRAFT, 'Draft'),
        (const.STATE_SENT, 'Sent'),
        (const.STATE_DONE, 'Successful'),
        (const.STATE_FAILED, 'Failed'),
        (const.STATE_TIMEOUT, 'Awaiting Confirmation'),
    ], default=const.STATE_DRAFT, required=True, copy=False, index=True)

    # -- TAECEL identifiers ------------------------------------------------
    trans_id = fields.Char(
        string='Transaction Handle', copy=False, index=True,
        help='TransID returned by TAECEL; the key that matches this sale in '
             'getSales without dispatching again.')
    folio = fields.Char(copy=False, help='TAECEL folio, printed on the receipt.')
    authorization = fields.Char(copy=False, help='Carrier authorization code.')
    pin = fields.Char(copy=False, help='PIN delivered by TAECEL, when applicable.')
    receipt_note = fields.Text(
        help='Text TAECEL requires on the customer receipt (carrier terms, '
             'balance query codes, PIN redemption instructions).')
    error_message = fields.Char(copy=False)

    # -- POS links ---------------------------------------------------------
    pos_order_id = fields.Many2one('pos.order', ondelete='set null', index=True)
    pos_order_line_id = fields.Many2one('pos.order.line', ondelete='set null')
    # Indexed: every open register polls this column every few seconds looking
    # for outcomes its cashier still has to act on.
    pos_session_id = fields.Many2one('pos.session', ondelete='set null', index=True)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user)
    sent_date = fields.Datetime(copy=False)
    done_date = fields.Datetime(copy=False)
    attempt_count = fields.Integer(default=0, copy=False,
                                   help='Reconciliation queries made, not dispatches.')
    cashier_alert_date = fields.Datetime(
        string='Acknowledged at Register', copy=False, readonly=True,
        help='When the register acknowledged a bad outcome. Empty on a '
             'transaction that failed means nobody at the counter has been '
             'told yet -- that is money taken for a recharge never delivered.')

    raw_request = fields.Text(copy=False, groups='point_of_sale.group_pos_manager')
    raw_response = fields.Text(copy=False, groups='point_of_sale.group_pos_manager')

    @api.depends('amount', 'customer_fee')
    def _compute_total_charged(self):
        for txn in self:
            txn.total_charged = txn.amount + txn.customer_fee

    @api.depends('product_id', 'reference', 'folio')
    def _compute_display_name(self):
        for txn in self:
            label = txn.product_id.display_name or txn.product_code or _('TAECEL')
            txn.display_name = '%s - %s%s' % (
                label, txn.reference or '',
                ' (%s)' % txn.folio if txn.folio else '')

    # -- Settlement from getSales (CONFIRMED path) -------------------------
    def _settle_from_sale(self, sale):
        """Resolve this transaction from a getSales row.

        Status comes padded from TAECEL ('Fracasada ') and cased freely, so we
        normalise before comparing.
        """
        self.ensure_one()
        status = str(sale.get(const.K_SALE_STATUS) or '').strip().lower()
        note = sale.get(const.K_SALE_NOTE) or ''
        self.raw_response = repr(sale)

        if status == const.SALE_STATUS_OK:
            self.write({
                'state': const.STATE_DONE,
                'folio': sale.get(const.K_SALE_FOLIO) or self.folio,
                'pin': sale.get(const.K_SALE_PIN) or self.pin,
                'receipt_note': note or self.receipt_note,
                'done_date': fields.Datetime.now(),
                'error_message': False,
            })
            return const.STATE_DONE
        if status == const.SALE_STATUS_KO:
            return self._mark_failed(note or _('Declined by TAECEL.'))
        # Present but not yet in a terminal state -- leave it for the next pass.
        return self.state

    def action_query_status(self):
        """Reconcile this one transaction now, via its account's getSales."""
        self.ensure_one()
        self.attempt_count += 1
        self.account_id.action_refresh_from_sales()
        return self.state

    def _mark_failed(self, message):
        self.ensure_one()
        self.write({'state': const.STATE_FAILED, 'error_message': message})
        return const.STATE_FAILED

    def _mark_timeout(self, message):
        self.ensure_one()
        self.write({'state': const.STATE_TIMEOUT, 'error_message': message})
        return const.STATE_TIMEOUT

    # -- Dispatch (CONFIRMED transactional API) ----------------------------
    def action_dispatch(self):
        """Send this transaction to TAECEL and settle it.

        The one hard rule: **never dispatch twice.** Once RequestTXN returns a
        transID the state moves to ``sent`` and the outcome is only ever read
        back with StatusTXN. A transport timeout or an unresolved poll parks the
        transaction (``timeout``) for the getSales reconciler -- it is not
        re-sent, because the recharge may already have reached the phone.
        """
        self.ensure_one()
        # Terminal outcomes never touch TAECEL again.
        if self.state in (const.STATE_DONE, const.STATE_FAILED):
            return self.state
        # Already dispatched (sent, or parked as timeout): the recharge may have
        # reached the phone, so resolve ONLY by re-querying its handle -- never
        # by sending again. Without a handle there is nothing safe to do.
        if self.state in (const.STATE_SENT, const.STATE_TIMEOUT):
            if self.trans_id:
                return self._poll_status(self.account_id.sudo()._get_client())
            return self.state

        account = self.account_id.sudo()
        client = account._get_client()
        # 'monto' is sent only for free-amount carriers; catalog products ignore it.
        send_amount = self.amount if self.carrier_id.carrier_type == const.CARRIER_FREE else None

        self.write({
            'state': const.STATE_SENT,
            'sent_date': fields.Datetime.now(),
            'attempt_count': self.attempt_count + 1,
        })
        result = client.request_txn(
            self.product_code, self.reference,
            amount=send_amount, ref_cliente=str(self.id))
        self.raw_response = repr(result.raw)

        if result.timed_out:
            return self._mark_timeout(result.message)
        if not result.ok:
            return self._mark_failed(result.message or _('TAECEL declined the request.'))

        data = result.data or {}
        trans_id = data.get(const.K_TXN_TRANS_ID) or data.get(const.K_SALE_TRANS_ID)
        if not trans_id:
            return self._mark_timeout(
                _('TAECEL accepted the request but returned no transID.'))
        self.write({'trans_id': str(trans_id)})
        return self._poll_status(client)

    def _poll_status(self, client):
        """Poll StatusTXN until the transaction resolves or the budget runs out.

        StatusTXN's ``data`` is shaped exactly like a getSales row, so the
        outcome is decided by ``data.Status`` (NOT the top-level ``success``,
        which only reports that the query itself worked). 'Exitosa' -> done,
        'Fracasada' -> failed, 'En proceso' (or anything else) -> keep polling
        while under DISPATCH_POLL_MAX, then park for the getSales reconciler.
        The whole thing is settled by the same code as getSales.
        """
        self.ensure_one()
        waited = 0
        while True:
            result = client.status_txn(self.trans_id)
            self.attempt_count += 1
            if result.timed_out:
                return self._mark_timeout(result.message)
            data = result.data or {}
            if data:
                outcome = self._settle_from_sale(data)
                if outcome == const.STATE_DONE:
                    self._refresh_wallet_from_row(data)
                    return outcome
                if outcome == const.STATE_FAILED:
                    return outcome
                # else: 'En proceso' -- _settle_from_sale left the state as-is.
            if waited >= const.DISPATCH_POLL_MAX:
                return self._mark_timeout(
                    _('TAECEL did not confirm in time; parked for reconciliation.'))
            time.sleep(const.DISPATCH_POLL_INTERVAL)
            waited += const.DISPATCH_POLL_INTERVAL

    def _refresh_wallet_from_row(self, row):
        """Push the 'Saldo Final' of a settled StatusTXN/getSales row onto the
        wallet, so the POS balance guard stays fresh without a getBalance call."""
        self.ensure_one()
        saldo = row.get(const.K_SALE_FINAL_BALANCE)
        if saldo not in (None, '') and self.bolsa_id:
            self.account_id._wallet(self.bolsa_id).write({
                'balance': _money(saldo),
                'balance_date': fields.Datetime.now(),
            })

    # -- Dispatcher cron ---------------------------------------------------
    @api.model
    def _cron_dispatch(self):
        """Dispatch transactions still in draft (created at POS payment).

        Kept separate from _cron_reconcile: dispatch sends, reconcile only
        reads. One transaction per commit so a mid-run error never re-sends a
        neighbour.
        """
        drafts = self.search([('state', '=', const.STATE_DRAFT)], limit=100)
        for txn in drafts:
            try:
                txn.action_dispatch()
                self.env.cr.commit()
            except Exception:  # noqa: BLE001 - one bad txn must not stop the run
                self.env.cr.rollback()
                _logger.exception('TAECEL dispatch failed for txn %s', txn.id)
        return True

    # -- Reconciler --------------------------------------------------------
    @api.model
    def _cron_reconcile(self):
        """Resolve transactions left in an unknown state, via getSales.

        Runs often and cheaply. Groups by account so each account is pulled
        once per bolsa rather than once per transaction.
        """
        pending = self.search([
            ('state', 'in', [const.STATE_SENT, const.STATE_TIMEOUT]),
        ], limit=500)
        for account in pending.mapped('account_id'):
            try:
                account.action_refresh_from_sales()
                self.env.cr.commit()
            except Exception:  # noqa: BLE001 - one bad account must not stop the run
                self.env.cr.rollback()
                _logger.exception('TAECEL reconcile failed for account %s', account.id)
        return True

    # -- POS ---------------------------------------------------------------
    @api.model
    def xb_pos_alerts(self, session_id):
        """Outcomes the cashier of this session still has to act on.

        Dispatch is asynchronous by design -- calling TAECEL while the customer
        waits would put a service that answers in up to 60s in the middle of
        every checkout. The cost of that choice is that a rejected recharge
        lands after the ticket is printed and the screen has moved on, so
        nobody at the counter learns the customer paid for nothing. This is the
        register's way of finding out: it polls, and a failure raises a popup
        while the customer is still there.

        Only non-terminal-for-the-cashier outcomes are returned, and only until
        acknowledged, so a browser reload cannot lose the warning.
        """
        alerts = self.search([
            ('pos_session_id', '=', session_id),
            ('state', 'in', (const.STATE_FAILED, const.STATE_TIMEOUT)),
            ('cashier_alert_date', '=', False),
        ])
        return [{
            'id': alert.id,
            'state': alert.state,
            'label': alert.product_id.display_name or alert.product_code or '',
            'reference': alert.reference or '',
            'amount': alert.total_charged,
            'error': alert.error_message or '',
        } for alert in alerts]

    @api.model
    def xb_pos_ack_alerts(self, txn_ids):
        """Stamp the warnings the cashier has just been shown.

        Stamped on dismissal rather than on display: an alert the cashier never
        saw -- a reload, a crash mid-popup -- has to come back.
        """
        alerts = self.browse(txn_ids).exists().filtered(
            lambda t: not t.cashier_alert_date)
        alerts.sudo().write({'cashier_alert_date': fields.Datetime.now()})
        return True

    @api.model
    def _load_pos_data_domain(self, data, config=None):
        return [('create_date', '>=', fields.Date.context_today(self))]

    @api.model
    def _load_pos_data_fields(self, config=None):
        return ['id', 'reference', 'amount', 'customer_fee', 'total_charged',
                'state', 'folio', 'pin', 'receipt_note', 'product_id',
                'pos_order_id']
