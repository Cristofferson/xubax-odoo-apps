from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

PAGE_SIZE = 100
MAX_PAGES = 100  # 10,000 payments: a month of a busy shop.
STATUSES = ['CONFIRMED', 'REFUNDED']
VAT_ON_FEE = 0.16


class PosXpagoReconcile(models.TransientModel):
    """Compares, for some days, the payments XPago took with the ones Odoo recorded."""
    _name = 'pos.xpago.reconcile'
    _description = "XPago reconciliation"

    provider_id = fields.Many2one(
        'payment.provider', string="XPago account", required=True, domain="[('code', '=', 'xpago')]",
        default=lambda self: self.env['payment.provider'].search(
            [('code', '=', 'xpago'), ('company_id', 'in', self.env.company.parent_ids.ids)], order='company_id desc', limit=1),
    )
    currency_id = fields.Many2one(related='provider_id.main_currency_id')
    date_from = fields.Date(string="From", required=True, default=lambda self: fields.Date.context_today(self) - timedelta(days=7))
    date_to = fields.Date(string="To", required=True, default=fields.Date.context_today)
    line_ids = fields.One2many('pos.xpago.reconcile.line', 'reconcile_id')

    def action_reconcile(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("The start date is after the end date."))
        start, end = self._utc_bounds()
        try:
            payments = self._fetch_payments(start, end)
        except ValidationError as error:
            raise UserError(_("XPago did not answer: %s", error)) from error
        self.line_ids = [fields.Command.clear()] + [fields.Command.create(values) for values in self._lines(payments, start, end)]
        return {
            'type': 'ir.actions.act_window',
            'name': _("XPago reconciliation %(start)s – %(end)s", start=self.date_from, end=self.date_to),
            'res_model': 'pos.xpago.reconcile.line',
            'view_mode': 'list,pivot',
            'domain': [('reconcile_id', '=', self.id)],
            'context': {'search_default_problems': 1},
        }

    def _utc_bounds(self):
        tz = ZoneInfo(self.env.user.tz or 'America/Mexico_City')
        start = datetime.combine(self.date_from, time.min, tzinfo=tz).astimezone(UTC).replace(tzinfo=None)
        end = datetime.combine(self.date_to, time.max, tzinfo=tz).astimezone(UTC).replace(tzinfo=None)
        return start, end

    def _fetch_payments(self, start, end):
        provider = self.provider_id.sudo()
        params = {
            'limit': PAGE_SIZE,
            'status': STATUSES,
            'createdAtFrom': start.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'createdAtTo': end.strftime('%Y-%m-%dT%H:%M:%S.999Z'),
        }
        payments = []
        for _page in range(MAX_PAGES):
            answer = provider._send_api_request('GET', '/developer/v1/payment', params=params)
            payments += answer.get('data') or []
            cursor = (answer.get('pagination') or {}).get('nextCursor')
            if not cursor:
                return payments
            params = {**params, 'cursor': cursor}
        raise UserError(_("Too many payments in these days: choose fewer days."))

    def _lines(self, payments, start, end):
        """One line per payment XPago took, matched to its Odoo record, plus one per Odoo record XPago does not
        know."""
        provider = self.provider_id
        Charge = self.env['pos.xpago.charge'].sudo()
        Tx = self.env['payment.transaction'].sudo()
        charges = Charge.search([('provider_id', '=', provider.id),
                                 ('xpago_id', 'in', [p['paymentIntentId'] for p in payments if p.get('paymentIntentId')])])
        charges_by_id = {charge.xpago_id: charge for charge in charges}
        refs = [p.get('oneTimePaymentId') for p in payments if p.get('oneTimePaymentId')] + [p['id'] for p in payments if p.get('id')]
        txs = Tx.search([('provider_id', '=', provider.id), ('provider_reference', 'in', refs)])
        txs_by_ref = {tx.provider_reference: tx for tx in txs}
        accounts = {account.xpago_id: account for account in self.env['payment.xpago.bank.account'].sudo().with_context(
            active_test=False).search([('provider_id', '=', provider.id)])}
        lines, seen_charges, seen_txs = [], Charge, Tx
        for payment in payments:
            charge = charges_by_id.get(payment.get('paymentIntentId')) or Charge
            tx = Tx if charge else (txs_by_ref.get(payment.get('id')) or txs_by_ref.get(payment.get('oneTimePaymentId')) or Tx)
            seen_charges |= charge
            seen_txs |= tx
            lines.append(self._line_from_payment(payment, charge, tx, accounts))
        for charge in Charge.search([('provider_id', '=', provider.id), ('state', '=', 'confirmed'),
                                     ('create_date', '>=', start), ('create_date', '<=', end)]) - seen_charges:
            lines.append(self._line_odoo_only(charge.create_date, charge.amount, 'pos', charge=charge))
        for tx in Tx.search([('provider_id', '=', provider.id), ('state', '=', 'done'), ('operation', '!=', 'refund'),
                             ('source_transaction_id', '=', False), ('create_date', '>=', start), ('create_date', '<=', end)]) - seen_txs:
            lines.append(self._line_odoo_only(tx.create_date, tx.amount, 'online', tx=tx))
        return lines

    def _line_from_payment(self, payment, charge, tx, accounts):
        amount = float(payment.get('amount') or 0)
        charged = float(payment.get('chargedAmount') or amount)
        fee = payment.get('fee')
        fee_amount = round(charged * fee / 100, 2) if isinstance(fee, (int, float)) else 0.0
        refunded = payment.get('status') == 'REFUNDED'
        if charge:
            source, odoo_amount, odoo_paid = 'pos', charge.amount, charge.state == 'confirmed'
        elif tx:
            source, odoo_amount, odoo_paid = 'online', tx.amount, tx.state in ('done', 'authorized')
        else:
            source, odoo_amount, odoo_paid = 'other', 0.0, False
        if not charge and not tx:
            status = 'xpago_only'
        elif refunded:
            refunds = tx.child_transaction_ids.filtered(lambda t: t.operation == 'refund' and t.state == 'done') if tx else tx
            status = 'ok' if refunds else 'refunded_in_xpago'
        elif not odoo_paid:
            status = 'not_paid_in_odoo'
        elif self.currency_id.compare_amounts(odoo_amount, amount):
            status = 'amount_differs'
        else:
            status = 'ok'
        card = payment.get('card') or {}
        return {
            'date': _parse(payment.get('createdAt')),
            'operation_code': str(payment.get('operationCode') or ''),
            'source': source,
            'status': status,
            'xpago_status': payment.get('status'),
            'xpago_amount': amount,
            'tip_amount': float(payment.get('tipAmount') or 0),
            'charged_amount': charged,
            'odoo_amount': odoo_amount,
            'fee_percent': fee if isinstance(fee, (int, float)) else 0.0,
            'fee_amount': fee_amount,
            'fee_vat': round(fee_amount * VAT_ON_FEE, 2),
            'terms': payment.get('terms') or 1,
            'bank_account_id': accounts.get(payment.get('bankAccountId')).id if accounts.get(payment.get('bankAccountId')) else False,
            'card': ' '.join(part for part in [card.get('network'), card.get('lastFourDigits')] if part),
            'charge_id': charge.id or False,
            'transaction_id': tx.id or False,
            'pos_order_id': charge.sale_order_id.id if charge else False,
            'reference': (tx.reference if tx else '') or (charge.sale_order_id.name if charge else '') or (charge.external_id if charge else ''),
        }

    def _line_odoo_only(self, date, amount, source, charge=None, tx=None):
        return {
            'date': date,
            'source': source,
            'status': 'odoo_only',
            'odoo_amount': amount,
            'charge_id': charge.id if charge else False,
            'transaction_id': tx.id if tx else False,
            'pos_order_id': charge.sale_order_id.id if charge else False,
            'reference': (tx.reference if tx else '') or (charge.sale_order_id.name or charge.external_id if charge else ''),
        }


class PosXpagoReconcileLine(models.TransientModel):
    _name = 'pos.xpago.reconcile.line'
    _description = "XPago reconciliation line"
    _order = 'date desc, id desc'

    reconcile_id = fields.Many2one('pos.xpago.reconcile', required=True, ondelete='cascade', index=True)
    currency_id = fields.Many2one(related='reconcile_id.currency_id')
    date = fields.Datetime(readonly=True)
    operation_code = fields.Char(string="Operation", readonly=True,
                                 help="The number printed on the voucher and shown in the XPago dashboard.")
    reference = fields.Char(string="Odoo reference", readonly=True)
    source = fields.Selection([('pos', "Terminal"), ('online', "Online"), ('other', "Other (dashboard, links)")], readonly=True)
    status = fields.Selection([
        ('ok', "Matches"),
        ('xpago_only', "Only in XPago"),
        ('odoo_only', "Only in Odoo"),
        ('not_paid_in_odoo', "Paid in XPago, not in Odoo"),
        ('amount_differs', "Amount differs"),
        ('refunded_in_xpago', "Refunded in XPago, not in Odoo"),
    ], string="Result", readonly=True)
    xpago_status = fields.Char(string="XPago status", readonly=True)
    xpago_amount = fields.Monetary(string="Sale in XPago", readonly=True)
    tip_amount = fields.Monetary(string="Tip", readonly=True)
    charged_amount = fields.Monetary(string="Charged to the card", readonly=True)
    odoo_amount = fields.Monetary(string="In Odoo", readonly=True)
    fee_percent = fields.Float(string="Fee %", readonly=True, digits=(5, 2),
                               help="XPago's rate before promotions: a promotion can make the real fee lower.")
    fee_amount = fields.Monetary(string="Fee", readonly=True, help="Charged amount × fee %, without VAT.")
    fee_vat = fields.Monetary(string="VAT on fee", readonly=True)
    terms = fields.Integer(string="Months", readonly=True)
    card = fields.Char(readonly=True)
    bank_account_id = fields.Many2one('payment.xpago.bank.account', string="Deposited in", readonly=True)
    charge_id = fields.Many2one('pos.xpago.charge', string="Terminal charge", readonly=True)
    transaction_id = fields.Many2one('payment.transaction', string="Online payment", readonly=True)
    pos_order_id = fields.Many2one('pos.order', string="Order", readonly=True)


def _parse(value):
    if not value:
        return False
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return parsed.astimezone(UTC).replace(tzinfo=None, microsecond=0)
