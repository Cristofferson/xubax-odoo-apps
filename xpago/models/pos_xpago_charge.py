import logging
import uuid
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_amount


_logger = logging.getLogger(__name__)

FINAL_STATES = ('confirmed', 'cancelled', 'expired', 'refunded')
# A paid charge gets its sale a moment later, when the cashier validates the order.
ORPHAN_GRACE = timedelta(minutes=10)


class PosXpagoCharge(models.Model):
    """A charge sent to an XPago terminal from the point of sale, and what the terminal answered."""
    _name = 'pos.xpago.charge'
    _description = "XPago terminal charge"
    _order = 'id desc'
    _rec_name = 'external_id'

    external_id = fields.Char(string="Reference", required=True, readonly=True, index=True)
    xpago_id = fields.Char(string="XPago id", readonly=True, index=True, copy=False)
    state = fields.Selection([
        ('pending', "Waiting for the card"),
        ('confirmed', "Paid"),
        ('cancelled', "Cancelled"),
        ('expired', "Expired"),
        ('refunded', "Refunded"),
    ], default='pending', required=True, readonly=True, index=True)
    amount = fields.Monetary(required=True, readonly=True)
    currency_id = fields.Many2one('res.currency', required=True, readonly=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True, index=True)
    payment_method_id = fields.Many2one('pos.payment.method', required=True, readonly=True, ondelete='cascade')
    provider_id = fields.Many2one('payment.provider', required=True, readonly=True, ondelete='cascade')
    session_id = fields.Many2one('pos.session', readonly=True, ondelete='set null')
    config_id = fields.Many2one('pos.config', string="Point of sale", readonly=True, ondelete='set null')
    order_uuid = fields.Char(readonly=True, index=True)
    pos_order_id = fields.Many2one('pos.order', string="Order", readonly=True, ondelete='set null',
                                   help="Orders paid at a self-order kiosk, which the charge itself completes.")
    terminal_serial = fields.Char(string="Terminal S/N", readonly=True)
    terminal_app_url = fields.Char(readonly=True, help="Opens the charge app when the point of sale runs on the terminal.")
    refunded_at = fields.Datetime(readonly=True)
    expires_at = fields.Datetime(readonly=True)
    card_brand = fields.Char(readonly=True)
    card_type = fields.Char(readonly=True)
    card_no = fields.Char(string="Card (last 4)", readonly=True)
    issuer_bank = fields.Char(readonly=True)
    entry_mode = fields.Char(readonly=True)
    authorization_code = fields.Char(readonly=True)
    operation_code = fields.Char(string="Operation", readonly=True)
    payment_id = fields.Char(string="Payment id", readonly=True)
    charged_amount = fields.Monetary(readonly=True, help="What the card was charged in total, the sale plus any tip.")
    tip_amount = fields.Monetary(string="Tip", readonly=True)
    terms = fields.Integer(string="Months without interest", readonly=True)
    notified = fields.Boolean(readonly=True, copy=False)
    pos_payment_id = fields.Many2one('pos.payment', string="Point of sale payment", compute='_compute_pos_payment')
    sale_order_id = fields.Many2one('pos.order', string="Sale", compute='_compute_pos_payment')
    without_sale = fields.Boolean(
        string="Paid without a sale", compute='_compute_pos_payment', search='_search_without_sale',
        help="The card was charged but no order of the point of sale holds the payment (for example, the sale was "
             "reloaded before the order was validated).",
    )
    bank_account_id = fields.Many2one('payment.xpago.bank.account', string="Deposit account", readonly=True,
                                      help="The account this charge was sent to.")

    def _compute_pos_payment(self):
        payments = self.env['pos.payment'].sudo().search([('transaction_id', 'in', [c.payment_id for c in self if c.payment_id])])
        for charge in self:
            payment = payments.filtered(
                lambda p: charge.payment_id and p.transaction_id == charge.payment_id and p.payment_method_id == charge.payment_method_id)[:1]
            charge.pos_payment_id = payment
            charge.sale_order_id = payment.pos_order_id or charge.pos_order_id
            charge.without_sale = charge.state == 'confirmed' and not charge.sale_order_id

    def _search_without_sale(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise UserError(_("Unsupported search on \"Paid without a sale\"."))
        self.env['pos.payment'].flush_model(['transaction_id', 'payment_method_id'])
        self.flush_model(['state', 'pos_order_id', 'payment_id', 'payment_method_id', 'create_date'])
        self.env.cr.execute("""
            SELECT charge.id
              FROM pos_xpago_charge charge
             WHERE charge.state = 'confirmed'
               AND charge.pos_order_id IS NULL
               AND charge.create_date < %s
               AND NOT EXISTS (SELECT 1 FROM pos_payment payment
                                WHERE payment.transaction_id = charge.payment_id
                                  AND payment.payment_method_id = charge.payment_method_id)
        """, [fields.Datetime.now() - ORPHAN_GRACE])
        ids = [row[0] for row in self.env.cr.fetchall()]
        positive = (operator == '=') == value
        return [('id', 'in' if positive else 'not in', ids)]

    # === CREATE AND READ BACK === #

    @api.model
    def _xpago_create(self, method, provider, amount, session, order_uuid, order=None, account=None):
        if amount <= 0:
            raise UserError(_("XPago terminals only charge positive amounts."))
        config = session.config_id
        currency = config.currency_id or method.company_id.currency_id or self.env.company.currency_id
        external_id = f"odoo-pos{config.id or 0}-{(order_uuid or '')[:8]}-{uuid.uuid4().hex[:6]}"
        charge = self.create({
            'external_id': external_id,
            'amount': currency.round(amount),
            'currency_id': currency.id,
            'company_id': (method.company_id or self.env.company).id,
            'payment_method_id': method.id,
            'provider_id': provider.id,
            'session_id': session.id,
            'config_id': config.id,
            'order_uuid': order_uuid,
            'terminal_serial': method.xpago_terminal_serial,
            'pos_order_id': order.id if order else False,
            'bank_account_id': account.id if account else False,
        })
        body = {
            'amount': charge.amount,
            'currency': currency.name,
            'reference': external_id,
            'terminal_serial': method.xpago_terminal_serial,
        }
        if account:
            body['deposit_account_id'] = account.xpago_id
        if config.xpago_print_on_terminal:
            body['print_voucher'] = False
        try:
            remote = provider._xpago_make_request('POST', '/v1/terminal-charges', json=body, idempotency_key=external_id)
        except ValidationError as error:
            raise UserError(_("XPago did not send the charge to the terminal.\n%s", error)) from error
        charge._xpago_apply(remote)
        return charge

    def _xpago_refresh(self):
        """Ask XPago for the charges still open. Returns the ones whose state changed."""
        changed = self.browse()
        for charge in self.filtered(lambda c: c.state not in FINAL_STATES and c.xpago_id):
            try:
                remote = charge.provider_id._xpago_make_request('GET', f'/v1/terminal-charges/{charge.xpago_id}')
            except ValidationError as error:
                _logger.warning("XPago: could not read the charge %s: %s", charge.external_id, error)
                continue
            if charge._xpago_apply(remote):
                changed |= charge
        changed._xpago_on_state_changed()
        return changed

    def _xpago_cancel(self):
        self.ensure_one()
        if self.state in FINAL_STATES:
            return
        try:
            remote = self.provider_id._xpago_make_request('POST', f'/v1/terminal-charges/{self.xpago_id}/cancel')
        except ValidationError:
            # Already paid or gone on the terminal: what XPago says now is what stays.
            self._xpago_refresh()
            return
        if self._xpago_apply(remote):
            self._xpago_on_state_changed()

    def _xpago_apply(self, remote):
        """Map XPago's answer onto the charge; True when its state changed."""
        self.ensure_one()
        state = {'paid': 'confirmed', 'canceled': 'cancelled', 'expired': 'expired', 'refunded': 'refunded'}.get(
            remote.get('status'), 'pending')
        if self.state == 'refunded':
            state = 'refunded'  # a refund is final, whatever an older answer says
        values = {}
        if remote.get('id') and not self.xpago_id:
            values['xpago_id'] = remote['id']
        if remote.get('terminal_app_url') and remote['terminal_app_url'] != self.terminal_app_url:
            values['terminal_app_url'] = remote['terminal_app_url']
        if remote.get('expires_at'):
            values['expires_at'] = _parse_datetime(remote['expires_at'])
        if remote.get('refunded_at') and not self.refunded_at:
            values['refunded_at'] = _parse_datetime(remote['refunded_at'])
        if state != self.state:
            values['state'] = state
        payment = remote.get('payment') or {}
        if state in ('confirmed', 'refunded') and payment and not self.payment_id:
            card = payment.get('card') or {}
            values.update({
                'payment_id': payment.get('id') or False,
                'operation_code': payment.get('operation_code') or False,
                'authorization_code': payment.get('authorization_code') or False,
                'card_brand': card.get('brand') or False,
                'card_type': card.get('funding') or False,
                'card_no': card.get('last4') or False,
                'issuer_bank': card.get('issuer') or False,
                'entry_mode': card.get('entry_mode') or False,
            })
            for field in ('charged_amount', 'tip_amount'):
                if isinstance(payment.get(field), (int, float)):
                    values[field] = payment[field]
            if isinstance(payment.get('installments'), int) and payment['installments'] > 1:
                values['terms'] = payment['installments']
        if values:
            self.write(values)
        return 'state' in values

    def _xpago_refund(self):
        """Give the whole charge back to the same card. XPago refunds a terminal charge the same day only."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_("Only a paid terminal charge can be refunded."))
        try:
            answer = self.provider_id._xpago_make_request('POST', f'/v1/terminal-charges/{self.xpago_id}/refund',
                                                        idempotency_key=f'refund-{self.external_id}')
        except ValidationError as error:
            # Refunded meanwhile on the terminal app or the dashboard: done, nothing more to send.
            if self._xpago_read_refunded():
                return {}
            refusal = UserError(_("XPago did not refund the charge.\n%s", error))
            refusal.xpago_code = getattr(error, 'xpago_code', None)
            raise refusal from error
        self.write({'state': 'refunded', 'refunded_at': fields.Datetime.now()})
        return answer

    def _xpago_read_refunded(self):
        """Ask XPago whether this paid charge was refunded outside Odoo (terminal app, dashboard). True when it was."""
        self.ensure_one()
        if not self.xpago_id:
            return False
        try:
            remote = self.provider_id._xpago_make_request('GET', f'/v1/terminal-charges/{self.xpago_id}')
        except ValidationError as error:
            _logger.warning("XPago: could not read the charge %s: %s", self.external_id, error)
            return False
        if remote.get('status') != 'refunded':
            return False
        self._xpago_apply(remote)
        if not self.refunded_at:
            self.refunded_at = fields.Datetime.now()
        return self.state == 'refunded'

    def action_xpago_refund(self):
        """Back office: refund a charge paid today, for example a sale cancelled after paying."""
        if not self.env.user.has_group('point_of_sale.group_pos_manager'):
            raise UserError(_("Only point of sale managers can refund terminal charges."))
        for charge in self:
            charge.sudo()._xpago_refund()
        return True

    def _xpago_on_state_changed(self):
        self._xpago_complete_orders()
        for charge in self.filtered(lambda c: c.state == 'confirmed' and not c.notified):
            charge.notified = True
            title = _("Payment received: %s", format_amount(self.env, charge.charged_amount or charge.amount, charge.currency_id))
            card = ' '.join(part for part in (charge.card_brand, charge.card_no and f'•••• {charge.card_no}') if part)
            lines = [
                _("Terminal at %s", charge.config_id.name) if charge.config_id else charge.payment_method_id.name,
                card,
                charge.terms > 1 and _("%s months without interest", charge.terms),
                charge.bank_account_id and _("Deposited in %s", charge.bank_account_id.name),
            ]
            charge.provider_id._xpago_notify(title, lines)

    def _xpago_complete_orders(self):
        """Hook for orders a charge pays by itself (self-order kiosk)."""

    def _xpago_payment_values(self):
        """The card of an approved charge, as the point of sale payment stores it."""
        self.ensure_one()
        return {
            'transaction_id': self.payment_id or '',
            'payment_ref_no': self.operation_code or '',
            'payment_method_authcode': self.authorization_code or '',
            'card_type': self.card_type or '',
            'card_brand': self.card_brand or '',
            'card_no': self.card_no or '',
            'payment_method_issuer_bank': self.issuer_bank or '',
            'payment_method_payment_mode': self.entry_mode or '',
        }

    def _xpago_public_view(self):
        """What the point of sale sees of the charge."""
        self.ensure_one()
        return {
            'id': self.id,
            'xpago_id': self.xpago_id,
            'state': self.state,
            'terminal_app_url': self.terminal_app_url or False,
            'expires_at': fields.Datetime.to_string(self.expires_at) if self.expires_at else False,
            'payment': self._xpago_payment_values() if self.state == 'confirmed' else {},
        }

    @api.model
    def _xpago_cron_refresh(self):
        """Read back the charges left open (a closed browser, a lost connection), and expire the old ones."""
        open_charges = self.search([('state', '=', 'pending'), ('create_date', '>', fields.Datetime.now() - timedelta(days=2))])
        open_charges._xpago_refresh()
        # The paid ones of the last day too: a refund made on the terminal app shows up here.
        for charge in self.sudo().search([('state', '=', 'confirmed'), ('create_date', '>', fields.Datetime.now() - timedelta(days=1))]):
            charge._xpago_read_refunded()
        self.search([('state', '=', 'pending'), ('create_date', '<=', fields.Datetime.now() - timedelta(days=2))]).write(
            {'state': 'expired'})


def _parse_datetime(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)
    except (TypeError, ValueError):
        return False
