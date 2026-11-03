import uuid
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_amount

from odoo.addons.payment.logging import get_payment_logger

_logger = get_payment_logger(__name__)

FINAL_STATES = ('confirmed', 'cancelled', 'expired')


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
    ], default='pending', required=True, readonly=True, index=True)
    amount = fields.Monetary(required=True, readonly=True)
    currency_id = fields.Many2one('res.currency', required=True, readonly=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True, index=True)
    payment_method_id = fields.Many2one('pos.payment.method', required=True, readonly=True, ondelete='cascade')
    provider_id = fields.Many2one('payment.provider', required=True, readonly=True, ondelete='cascade')
    session_id = fields.Many2one('pos.session', readonly=True, ondelete='set null')
    config_id = fields.Many2one('pos.config', string="Point of sale", readonly=True, ondelete='set null')
    order_uuid = fields.Char(readonly=True, index=True)
    terminal_serial = fields.Char(string="Terminal S/N", readonly=True)
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

    # === CREATE AND READ BACK === #

    @api.model
    def _xpago_create(self, method, provider, amount, session, order_uuid):
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
        })
        body = {
            'amount': charge.amount,
            'currency': currency.name,
            'externalId': external_id,
            'terminalCode': method.xpago_terminal_serial,
        }
        try:
            remote = provider._send_api_request('POST', '/payment-intent', json=body)
        except ValidationError as error:
            raise UserError(_("XPago did not send the charge to the terminal.\n%s", error)) from error
        charge._xpago_apply(remote)
        return charge

    def _xpago_refresh(self):
        """Ask XPago for the charges still open. Returns the ones whose state changed."""
        changed = self.browse()
        for charge in self.filtered(lambda c: c.state not in FINAL_STATES and c.xpago_id):
            try:
                remote = charge.provider_id._send_api_request('GET', f'/payment-intent/{charge.xpago_id}')
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
            remote = self.provider_id._send_api_request('POST', f'/payment-intent/{self.xpago_id}/cancel')
        except ValidationError:
            # Already paid or gone on the terminal: what XPago says now is what stays.
            self._xpago_refresh()
            return
        if self._xpago_apply(remote):
            self._xpago_on_state_changed()

    def _xpago_apply(self, remote):
        """Map XPago's answer onto the charge; True when its state changed."""
        self.ensure_one()
        summary = remote.get('paymentSummary') or {}
        approved = summary.get('status') == 'SUCCESS' or remote.get('status') == 'CONFIRMED'
        if approved:
            state = 'confirmed'
        elif remote.get('status') == 'CANCELLED':
            state = 'cancelled'
        elif remote.get('expired'):
            state = 'expired'
        else:
            state = 'pending'
        values = {}
        if remote.get('id') and not self.xpago_id:
            values['xpago_id'] = remote['id']
        if remote.get('expiresAt'):
            values['expires_at'] = _parse_datetime(remote['expiresAt'])
        if state != self.state:
            values['state'] = state
        if approved:
            payment = summary.get('payment') or {}
            transaction = summary.get('paymentTransaction') or {}
            card = summary.get('cardInformation') or {}
            values.update({
                'payment_id': payment.get('id') or False,
                'operation_code': str(payment.get('operationCode') or '') or False,
                'authorization_code': transaction.get('resultCode') or False,
                'card_brand': card.get('networkType') or False,
                'card_type': card.get('fundingSource') or False,
                'card_no': card.get('lastFourDigits') or False,
                'issuer_bank': card.get('issuingBank') or False,
                'entry_mode': card.get('entryMode') or False,
            })
            for field, key in (('charged_amount', 'chargedAmount'), ('tip_amount', 'tipAmount')):
                if isinstance(payment.get(key), (int, float)):
                    values[field] = payment[key]
            if isinstance(payment.get('terms'), int) and payment['terms'] > 1:
                values['terms'] = payment['terms']
        if values:
            self.write(values)
        return 'state' in values

    def _xpago_on_state_changed(self):
        for charge in self.filtered(lambda c: c.state == 'confirmed' and not c.notified):
            charge.notified = True
            title = _("Payment received: %s", format_amount(self.env, charge.charged_amount or charge.amount, charge.currency_id))
            card = ' '.join(part for part in (charge.card_brand, charge.card_no and f'•••• {charge.card_no}') if part)
            lines = [
                _("Terminal at %s", charge.config_id.name) if charge.config_id else charge.payment_method_id.name,
                card,
                charge.terms > 1 and _("%s months without interest", charge.terms),
            ]
            charge.provider_id._xpago_notify(title, lines)

    def _xpago_public_view(self):
        """What the point of sale sees of the charge."""
        self.ensure_one()
        return {
            'id': self.id,
            'xpago_id': self.xpago_id,
            'state': self.state,
            'expires_at': fields.Datetime.to_string(self.expires_at) if self.expires_at else False,
            'payment': {
                'transaction_id': self.payment_id or '',
                'payment_ref_no': self.operation_code or '',
                'payment_method_authcode': self.authorization_code or '',
                'card_type': self.card_type or '',
                'card_brand': self.card_brand or '',
                'card_no': self.card_no or '',
                'payment_method_issuer_bank': self.issuer_bank or '',
                'payment_method_payment_mode': self.entry_mode or '',
            } if self.state == 'confirmed' else {},
        }

    @api.model
    def _xpago_cron_refresh(self):
        """Read back the charges left open (a closed browser, a lost connection), and expire the old ones."""
        open_charges = self.search([('state', '=', 'pending'), ('create_date', '>', fields.Datetime.now() - timedelta(days=2))])
        open_charges._xpago_refresh()
        self.search([('state', '=', 'pending'), ('create_date', '<=', fields.Datetime.now() - timedelta(days=2))]).write(
            {'state': 'expired'})


def _parse_datetime(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)
    except (TypeError, ValueError):
        return False
