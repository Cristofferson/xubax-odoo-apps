import logging
import uuid
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_amount

from odoo.addons.xpago.models.pos_xpago_charge import ORPHAN_GRACE, _parse_datetime

_logger = logging.getLogger(__name__)

# A CLABE that expired can be renewed (the sale stays the same); the others end the transfer.
FINAL_STATES = ('paid', 'cancelled', 'returned')
STATES = {'awaiting': 'awaiting', 'paid': 'paid', 'expired': 'expired', 'canceled': 'cancelled', 'returned': 'returned'}
# How long the customer has to pay the sale by transfer (each CLABE lives 60 minutes inside it; an expired one is
# replaced by a new one while the sale is still open).
CHECKOUT_TTL_MINUTES = 24 * 60


class PosXpagoTransfer(models.Model):
    """A sale of the point of sale paid by SPEI transfer to a CLABE made for it alone."""
    _name = 'pos.xpago.transfer'
    _description = "XPago transfer (one-time CLABE)"
    _order = 'id desc'
    _rec_name = 'external_id'

    external_id = fields.Char(string="Reference", required=True, readonly=True, index=True)
    xpago_id = fields.Char(string="XPago id", readonly=True, index=True, copy=False,
                           help="The XPago payment page of this sale; the CLABE belongs to it.")
    state = fields.Selection([
        ('awaiting', "Waiting for the transfer"),
        ('paid', "Paid"),
        ('expired', "CLABE expired"),
        ('cancelled', "Cancelled"),
        ('returned', "Returned"),
        ('refunded', "Refunded"),
    ], default='awaiting', required=True, readonly=True, index=True)
    refunded_at = fields.Datetime(readonly=True, copy=False)
    amount = fields.Monetary(required=True, readonly=True)
    amount_received = fields.Monetary(string="Received", readonly=True,
                                      help="What has arrived so far: the customer may pay in several transfers.")
    amount_due = fields.Monetary(string="Missing", readonly=True)
    currency_id = fields.Many2one('res.currency', required=True, readonly=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True, index=True)
    payment_method_id = fields.Many2one('pos.payment.method', required=True, readonly=True, ondelete='cascade')
    provider_id = fields.Many2one('payment.provider', required=True, readonly=True, ondelete='cascade')
    session_id = fields.Many2one('pos.session', readonly=True, ondelete='set null')
    config_id = fields.Many2one('pos.config', string="Point of sale", readonly=True, ondelete='set null')
    order_uuid = fields.Char(readonly=True, index=True)
    bank_account_id = fields.Many2one('payment.xpago.bank.account', string="Deposit account", readonly=True)
    clabe = fields.Char(string="CLABE", readonly=True, help="The whole CLABE, only while it takes money.")
    clabe_last4 = fields.Char(string="CLABE (last 4)", readonly=True)
    bank = fields.Char(readonly=True)
    beneficiary = fields.Char(readonly=True)
    concept = fields.Char(readonly=True)
    checkout_url = fields.Char(string="Payment page", readonly=True,
                               help="The same CLABE on XPago's page, for a customer who would rather open it on the phone.")
    expires_at = fields.Datetime(string="CLABE valid until", readonly=True)
    paid_at = fields.Datetime(readonly=True)
    payment_id = fields.Char(string="Payment id", readonly=True)
    operation_code = fields.Char(string="Operation", readonly=True)
    customer_name = fields.Char(readonly=True)
    customer_email = fields.Char(readonly=True)
    customer_phone = fields.Char(readonly=True)
    notified = fields.Boolean(readonly=True, copy=False)
    pos_payment_id = fields.Many2one('pos.payment', string="Point of sale payment", compute='_compute_pos_payment')
    sale_order_id = fields.Many2one('pos.order', string="Sale", compute='_compute_pos_payment')
    without_sale = fields.Boolean(
        string="Paid without a sale", compute='_compute_pos_payment', search='_search_without_sale',
        help="The transfer arrived but no order of the point of sale holds the payment (for example, the sale was "
             "reloaded before the order was validated).",
    )

    def _compute_pos_payment(self):
        payments = self.env['pos.payment'].sudo().search(
            [('transaction_id', 'in', [t.payment_id for t in self if t.payment_id])])
        for transfer in self:
            payment = payments.filtered(lambda p: transfer.payment_id and p.transaction_id == transfer.payment_id
                                        and p.payment_method_id == transfer.payment_method_id)[:1]
            transfer.pos_payment_id = payment
            transfer.sale_order_id = payment.pos_order_id
            transfer.without_sale = transfer.state == 'paid' and not payment

    def _search_without_sale(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise UserError(_("Unsupported search on \"Paid without a sale\"."))
        self.env['pos.payment'].flush_model(['transaction_id', 'payment_method_id'])
        self.flush_model(['state', 'payment_id', 'payment_method_id', 'create_date'])
        self.env.cr.execute("""
            SELECT transfer.id
              FROM pos_xpago_transfer transfer
             WHERE transfer.state = 'paid'
               AND transfer.create_date < %s
               AND NOT EXISTS (SELECT 1 FROM pos_payment payment
                                WHERE payment.transaction_id = transfer.payment_id
                                  AND payment.payment_method_id = transfer.payment_method_id)
        """, [fields.Datetime.now() - ORPHAN_GRACE])
        ids = [row[0] for row in self.env.cr.fetchall()]
        positive = (operator == '=') == value
        return [('id', 'in' if positive else 'not in', ids)]

    # === CREATE AND READ BACK === #

    @api.model
    def _xpago_create(self, method, provider, amount, session, order_uuid, customer, account=None):
        """Create the XPago payment page of the sale, open to bank transfers only, with its CLABE made right away.
        ``customer``: email, first_name, last_name, phone (the CLABE is made out to whoever pays)."""
        if amount <= 0:
            raise UserError(_("A transfer only pays positive amounts."))
        customer = dict(customer)
        name = customer.pop('display_name', None) or ' '.join(
            dict.fromkeys(p for p in (customer.get('first_name'), customer.get('last_name')) if p))
        missing = [label for key, label in (('first_name', _("name")), ('email', _("email")), ('phone', _("phone")))
                   if not customer.get(key)]
        if missing:
            raise UserError(_("To make the CLABE, XPago needs who pays: %s.", ", ".join(missing)))
        config = session.config_id
        currency = config.currency_id or method.company_id.currency_id or self.env.company.currency_id
        company = config.company_id or method.company_id or self.env.company  # the branch that sells, e.g. Anello
        external_id = f"odoo-pos{config.id or 0}-spei-{(order_uuid or '')[:8]}-{uuid.uuid4().hex[:6]}"
        transfer = self.create({
            'external_id': external_id,
            'amount': currency.round(amount),
            'amount_due': currency.round(amount),
            'currency_id': currency.id,
            'company_id': company.id,
            'payment_method_id': method.id,
            'provider_id': provider.id,
            'session_id': session.id,
            'config_id': config.id,
            'order_uuid': order_uuid,
            'bank_account_id': account.id if account else False,
            'customer_name': name,
            'customer_email': customer.get('email'),
            'customer_phone': customer.get('phone'),
        })
        base_url = provider.get_base_url().rstrip('/')
        body = {
            'amount': transfer.amount,
            'currency': currency.name,
            'reference': external_id,
            'description': f"{company.name} – {config.name or _('Point of sale')}"[:255],
            'home_url': base_url,
            'return_url': base_url + '/payment/xpago/return',
            'expires_in_minutes': CHECKOUT_TTL_MINUTES,
            'customer': customer,
            'methods': ['bank_transfer'],
            # Not 'create': the processor then makes a SECOND CLABE ~11 s later on its own and reports only that one, so a
            # customer who copied the first pays a CLABE Odoo no longer sees (LAMUR 20-nov, $531). The CLABE is asked
            # for right below instead: one per sale, it does not change (tried live 20-nov).
            'bank_transfer_at': 'checkout',
        }
        if account:
            body['deposit_account_id'] = account.xpago_id
        try:
            created = provider._xpago_make_request('POST', '/v1/checkouts', json=body, idempotency_key=external_id)
        except ValidationError as error:
            raise UserError(_("XPago did not make the CLABE.\n%s", error)) from error
        transfer.xpago_id = created.get('id')
        clabe = created.get('bank_transfer')
        if not clabe:
            # The page is made without its CLABE (see above): ask for it now, once.
            clabe = transfer._xpago_request_clabe()
        transfer._xpago_apply(clabe or {})
        return transfer

    def _xpago_request_clabe(self):
        """The live CLABE of the sale, or a new one when the last one expired."""
        self.ensure_one()
        try:
            return self.provider_id._xpago_make_request(
                'POST', f'/v1/checkouts/{self.xpago_id}/bank-transfer',
                idempotency_key=f'clabe-{self.external_id}-{uuid.uuid4().hex[:6]}')
        except ValidationError as error:
            raise UserError(_("XPago did not make the CLABE.\n%s", error)) from error

    def _xpago_renew(self):
        """A new CLABE for a sale whose CLABE expired before the money arrived."""
        self.ensure_one()
        if self.state != 'expired':
            raise UserError(_("Only an expired CLABE is replaced."))
        if self._xpago_apply(self._xpago_request_clabe()):
            self._xpago_on_state_changed()

    def _xpago_refresh(self):
        """Ask XPago for the transfers still open. Returns the ones whose state changed."""
        changed = self.browse()
        for transfer in self.filtered(lambda t: t.state not in FINAL_STATES and t.xpago_id):
            try:
                remote = transfer.provider_id._xpago_make_request('GET', f'/v1/checkouts/{transfer.xpago_id}/bank-transfer')
                if remote.get('status') != 'paid':
                    remote = transfer._xpago_paid_checkout(remote)
            except ValidationError as error:
                _logger.warning("XPago: could not read the transfer %s: %s", transfer.external_id, error)
                continue
            if transfer._xpago_apply(remote):
                changed |= transfer
        changed._xpago_on_state_changed()
        return changed

    def _xpago_paid_checkout(self, remote):
        """The processor can mark the payment page paid while its CLABE still reads «awaiting» (or «canceled», with
        nothing received): the page is what says the money arrived. Returns the CLABE as paid in that case."""
        self.ensure_one()
        checkout = self.provider_id._xpago_make_request('GET', f'/v1/checkouts/{self.xpago_id}')
        if checkout.get('status') != 'paid':
            return remote
        _logger.info("XPago: the payment page of %s is paid while its CLABE reads %s", self.external_id,
                     remote.get('status'))
        payment = checkout.get('payment') or {}
        return dict(remote, status='paid', amount_received=self.amount, amount_due=0.0,
                    payment_id=remote.get('payment_id') or payment.get('id'),
                    paid_at=remote.get('paid_at') or payment.get('created_at') or payment.get('paid_at'))

    def _xpago_cancel(self):
        """Stop taking money for this sale. What already arrived is sent back by XPago."""
        self.ensure_one()
        if self.state in FINAL_STATES:
            return
        try:
            self.provider_id._xpago_make_request('POST', f'/v1/checkouts/{self.xpago_id}/cancel')
        except ValidationError:
            # Paid meanwhile: what XPago says now is what stays.
            self._xpago_refresh()
            return
        self.write({'state': 'cancelled', 'clabe': False, 'amount_due': 0.0})

    def _xpago_apply(self, remote):
        """Map XPago's CLABE onto the transfer; True when its state changed."""
        self.ensure_one()
        state = STATES.get(remote.get('status'), self.state)
        values = {}
        for field, key in (('clabe_last4', 'clabe_last4'), ('bank', 'bank'), ('beneficiary', 'beneficiary'),
                           ('concept', 'concept'), ('checkout_url', 'url')):
            if remote.get(key) and remote[key] != self[field]:
                values[field] = remote[key]
        # The whole CLABE is only shown while it takes money.
        clabe = remote.get('clabe') if state == 'awaiting' else False
        if (clabe or False) != (self.clabe or False):
            values['clabe'] = clabe or False
        for field in ('amount_received', 'amount_due'):
            if isinstance(remote.get(field), (int, float)):
                values[field] = remote[field]
        if remote.get('expires_at'):
            values['expires_at'] = _parse_datetime(remote['expires_at'])
        if remote.get('paid_at') and not self.paid_at:
            values['paid_at'] = _parse_datetime(remote['paid_at'])
        if remote.get('payment_id') and not self.payment_id:
            values['payment_id'] = remote['payment_id']
        if state != self.state:
            values['state'] = state
        if values:
            self.write(values)
        if state == 'paid' and not self.operation_code:
            self._xpago_read_operation()
        return 'state' in values

    def _xpago_read_operation(self):
        """The operation number of the paid transfer, from the payment page (the CLABE does not carry it)."""
        try:
            checkout = self.provider_id._xpago_make_request('GET', f'/v1/checkouts/{self.xpago_id}')
        except ValidationError as error:
            _logger.warning("XPago: could not read the payment of %s: %s", self.external_id, error)
            return
        payment = checkout.get('payment') or {}
        values = {}
        if payment.get('operation_code'):
            values['operation_code'] = payment['operation_code']
        if payment.get('id') and not self.payment_id:
            values['payment_id'] = payment['id']
        if values:
            self.write(values)

    def _xpago_on_state_changed(self):
        for transfer in self.filtered(lambda t: t.state == 'paid' and not t.notified):
            transfer.notified = True
            title = _("Transfer received: %s", format_amount(self.env, transfer.amount, transfer.currency_id))
            lines = [
                _("At %s", transfer.config_id.name) if transfer.config_id else transfer.payment_method_id.name,
                transfer.clabe_last4 and _("CLABE ending in %s", transfer.clabe_last4),
                transfer.customer_name,
                transfer.bank_account_id and _("Deposited in %s", transfer.bank_account_id.name),
            ]
            transfer.provider_id._xpago_notify(title, lines)

    def _xpago_payment_values(self):
        """The paid transfer, as the point of sale payment stores it."""
        self.ensure_one()
        return {
            'transaction_id': self.payment_id or self.xpago_id or '',
            'payment_ref_no': self.operation_code or '',
            'card_no': self.clabe_last4 or '',
            'card_type': 'SPEI',
            'payment_method_payment_mode': 'SPEI',
            'cardholder_name': self.customer_name or '',
        }

    def _xpago_public_view(self):
        """What the point of sale sees of the transfer."""
        self.ensure_one()
        return {
            'id': self.id,
            'state': self.state,
            'amount': self.amount,
            'amount_received': self.amount_received,
            'amount_due': self.amount_due,
            'clabe': self.clabe or '',
            'clabe_last4': self.clabe_last4 or '',
            'bank': self.bank or '',
            'beneficiary': self.beneficiary or '',
            'business': self.provider_id._xpago_business_name(),
            'concept': self.concept or '',
            'customer_phone': self.customer_phone or '',
            # The WhatsApp button shows only where the business uses WhatsApp (Odoo's WhatsApp app installed).
            'whatsapp': 'whatsapp.account' in self.env,
            'checkout_url': self.checkout_url or '',
            'expires_at': fields.Datetime.to_string(self.expires_at) if self.expires_at else False,
            'payment': self._xpago_payment_values() if self.state == 'paid' else {},
        }

    def _xpago_refund(self):
        """Give the whole transfer back to who paid. XPago refunds it the same day only (before 10:30 PM), in full;
        the processor keeps its fee from the sales pending to settle."""
        self.ensure_one()
        if self.state != 'paid':
            raise UserError(_("Only a paid transfer can be refunded."))
        try:
            answer = self.provider_id._xpago_make_request('POST', f'/v1/checkouts/{self.xpago_id}/refund',
                                                        idempotency_key=f'refund-{self.external_id}')
        except ValidationError as error:
            raise UserError(_("XPago did not refund the transfer.\n%s", error)) from error
        self.write({'state': 'refunded', 'refunded_at': fields.Datetime.now()})
        return answer

    @api.model
    def _xpago_cron_refresh(self):
        """Read back the transfers left open (a closed screen, a lost connection): a transfer can arrive late."""
        self = self.sudo()
        recent = fields.Datetime.now() - timedelta(minutes=CHECKOUT_TTL_MINUTES + 60)
        self.search([('state', 'in', ('awaiting', 'expired')), ('create_date', '>', recent)])._xpago_refresh()
        self.search([('state', 'in', ('awaiting', 'expired')), ('create_date', '<=', recent)]).write(
            {'state': 'cancelled', 'clabe': False})
