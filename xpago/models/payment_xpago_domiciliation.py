import calendar
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models, modules
from odoo.exceptions import UserError, ValidationError

PENDING_TX = ('draft', 'pending', 'authorized')
MAX_FAILURES = 3   # A declined invoice is not tried again after this many attempts.
RETRY_DAYS = 2     # Days between two automatic attempts on the same invoice.


class PaymentXpagoDomiciliation(models.Model):
    """The customer's permission to charge their saved card what they owe, and when."""
    _name = 'payment.xpago.domiciliation'
    _description = "Card on file charge"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'partner_id, id'

    name = fields.Char(compute='_compute_name', store=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    partner_id = fields.Many2one('res.partner', string="Customer", required=True, tracking=True,
                                 domain="[('parent_id', '=', False)]")
    token_id = fields.Many2one(
        'payment.token', string="Saved card", required=True, tracking=True, check_company=True,
        domain="[('partner_id', 'child_of', partner_id), ('active', '=', True)]",
        help="The customer saves it when they pay online with «Save my card», or from «My payment methods» in "
             "their portal.")
    state = fields.Selection([('active', "Active"), ('paused', "Paused")], default='active', required=True,
                             tracking=True)
    source = fields.Selection([
        ('invoices', "Pending invoices"),
        ('subscription', "Subscription"),
    ], string="What is charged", default='invoices', required=True, tracking=True,
        help="Pending invoices: what the customer owes in posted invoices.\n"
             "Subscription: the card pays the customer's subscriptions each time they renew (each month, year…, "
             "as the plan says), for the amount of the lines at that moment.")
    schedule = fields.Selection([
        ('manual', "By hand"),
        ('due', "When each invoice is due"),
        ('monthly', "Once a month"),
    ], string="When", default='monthly', required=True, tracking=True,
        help="By hand: you press «Charge now» here, or «Register payment» on the invoice with the saved card.\n"
             "When each invoice is due: every invoice is charged on its due date.\n"
             "Once a month: on the day you choose, everything invoiced until that day.")
    month_day = fields.Integer(string="Day of the month", default=31, tracking=True,
                               help="31 is the last day of each month, also in shorter months.")
    max_amount = fields.Monetary(string="Most per charge", tracking=True,
                                 help="What the customer agreed to as the most per charge. A larger amount is not "
                                      "charged: the person responsible gets a task to check it. 0 is no limit.")
    notify_customer = fields.Boolean(string="Email the customer each charge", default=True)
    user_id = fields.Many2one('res.users', string="Responsible", default=lambda self: self.env.user, tracking=True,
                              help="Gets a task when a charge is declined or goes over the most per charge.")
    authorized_on = fields.Date(string="Authorized on", default=fields.Date.context_today, tracking=True)
    authorization_note = fields.Text(string="How the customer authorized it",
                                     help="For example: signed form, email of the 3rd, call recorded…")
    next_date = fields.Date(string="Next charge", compute='_compute_next_date')
    transaction_ids = fields.One2many('payment.transaction', 'xpago_domiciliation_id', string="Charges")
    transaction_count = fields.Integer(compute='_compute_counts')
    pending_amount = fields.Monetary(string="Owed now", compute='_compute_counts')
    has_subscriptions = fields.Boolean(compute='_compute_has_subscriptions')

    _month_day = models.Constraint('CHECK(month_day BETWEEN 1 AND 31)', "The day of the month goes from 1 to 31.")

    @api.depends('partner_id', 'token_id')
    def _compute_name(self):
        for record in self:
            record.name = ' · '.join(filter(None, [record.partner_id.name, record.token_id.display_name]))

    def _compute_has_subscriptions(self):
        installed = self._subscriptions_installed()
        for record in self:
            record.has_subscriptions = installed

    @api.depends('schedule', 'month_day', 'source', 'state')
    def _compute_next_date(self):
        today = fields.Date.context_today(self)
        for record in self:
            date = False
            if record.state == 'active' and record.source == 'invoices':
                if record.schedule == 'monthly':
                    date = record._charge_day(today)
                    if date < today:
                        date = record._charge_day(today + relativedelta(months=1))
                elif record.schedule == 'due':
                    date = min(record._invoices_to_charge().mapped('invoice_date_due'), default=False)
                    date = date and max(date, today)
            elif record.state == 'active':
                date = min(record._subscriptions().mapped('next_invoice_date'), default=False) \
                    if record._subscriptions_installed() else False
            record.next_date = date

    def _compute_counts(self):
        for record in self:
            record.transaction_count = len(record.transaction_ids)
            record.pending_amount = sum(record._invoices_to_charge().mapped('amount_residual'))

    @api.constrains('partner_id', 'token_id')
    def _check_token(self):
        for record in self:
            if record.token_id.partner_id.commercial_partner_id != record.partner_id.commercial_partner_id:
                raise ValidationError(_("The saved card must belong to the customer."))

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        tokens = self.env['payment.token'].search(
            [('partner_id', 'child_of', self.partner_id.commercial_partner_id.id)], order='id desc', limit=1)
        if self.token_id.partner_id.commercial_partner_id != self.partner_id.commercial_partner_id:
            self.token_id = tokens

    # === SUBSCRIPTIONS === #

    def _subscriptions_installed(self):
        return 'sale.order' in self.env and 'is_subscription' in self.env['sale.order']._fields

    def _subscriptions(self):
        self.ensure_one()
        if not self._subscriptions_installed() or not self.partner_id:
            return self.env['sale.order'] if 'sale.order' in self.env else []
        return self.env['sale.order'].search([
            ('is_subscription', '=', True),
            ('partner_id', 'child_of', self.partner_id.commercial_partner_id.id),
            ('subscription_state', 'in', ['3_progress', '4_paused']),
            ('company_id', '=', self.company_id.id),
        ])

    def _gives_card(self):
        """Whether this record puts its card on the customer's subscriptions."""
        self.ensure_one()
        return self.active and self.state == 'active' and self.source == 'subscription'

    def _sync_subscriptions(self, gave=None):
        """The subscriptions renew on their own and pay with the card they carry: give it, or take it back only
        from a record that gave it. A card the customer saved on the subscription themselves is never touched."""
        gave = gave or {}
        for record in self.filtered(lambda r: r._subscriptions_installed()):
            subscriptions = record._subscriptions()
            if record._gives_card():
                subscriptions.filtered(lambda s: s.payment_token_id != record.token_id).payment_token_id = record.token_id
            elif gave.get(record.id):
                subscriptions.filtered(lambda s: s.payment_token_id == record.token_id).payment_token_id = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_subscriptions()
        return records

    def write(self, vals):
        gave = {}
        if {'token_id', 'partner_id', 'source', 'state', 'active'} & set(vals):
            gave = {record.id: record._gives_card() for record in self}
            if {'token_id', 'partner_id'} & set(vals):
                # Take the old card away from the old subscriptions before another one is set.
                for record in self.filtered(lambda r: gave[r.id] and r._subscriptions_installed()):
                    record._subscriptions().filtered(lambda s: s.payment_token_id == record.token_id).payment_token_id = False
        result = super().write(vals)
        if gave:
            self._sync_subscriptions(gave)
        return result

    def unlink(self):
        self.write({'active': False})
        return super().unlink()

    # === WHAT AND WHEN === #

    def _charge_day(self, date):
        """This record's charge day in the month of ``date``: the 31st is the last day of short months."""
        self.ensure_one()
        last = calendar.monthrange(date.year, date.month)[1]
        return date.replace(day=min(self.month_day or last, last))

    def _last_charge_day(self, today):
        day = self._charge_day(today)
        return day if day <= today else self._charge_day(today - relativedelta(months=1))

    def _invoices_to_charge(self, automatic=False):
        """The posted customer invoices still owed, without a charge already on its way."""
        self.ensure_one()
        if not self.partner_id or self.source != 'invoices':
            return self.env['account.move']
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
            ('amount_residual', '>', 0),
            ('commercial_partner_id', '=', self.partner_id.commercial_partner_id.id),
            ('company_id', '=', self.company_id.id),
            ('currency_id', '=', self.currency_id.id),
        ]
        if automatic:
            # The automatic charges cover what was invoiced since the customer authorized them; older debts are
            # charged with «Charge now».
            today = fields.Date.context_today(self)
            domain.append(('invoice_date', '>=', self.authorized_on or today))
            if self.schedule == 'due':
                domain.append(('invoice_date_due', '<=', today))
            elif self.schedule == 'monthly':
                domain.append(('invoice_date', '<=', self._last_charge_day(today)))
        invoices = self.env['account.move'].search(domain, order='invoice_date_due, id')
        busy = invoices.transaction_ids.filtered(lambda t: t.state in PENDING_TX).invoice_ids
        invoices -= busy
        if automatic:
            invoices = invoices.filtered(self._may_retry)
        return invoices

    def _may_retry(self, invoice):
        """A declined invoice waits a couple of days before the next try, and stops after a few."""
        failed = invoice.transaction_ids.filtered(
            lambda t: t.xpago_domiciliation_id and t.state in ('error', 'cancel'))
        if len(failed) >= MAX_FAILURES:
            return False
        last = max(failed.mapped('last_state_change'), default=False)
        return not last or fields.Datetime.now() - last >= timedelta(days=RETRY_DAYS)

    # === CHARGING === #

    def action_charge_now(self):
        declined = []
        for record in self:
            if record.state != 'active':
                raise UserError(_("The card on file charge of %s is paused.", record.partner_id.display_name))
            if record.source != 'invoices':
                raise UserError(_("The subscriptions are charged when they renew."))
            invoices = record._invoices_to_charge()
            if not invoices:
                raise UserError(_("%s owes nothing right now.", record.partner_id.display_name))
            tx = record._charge(invoices)
            if tx and tx.state == 'error':
                declined.append(_("The card was declined: %s", tx.state_message or _("no reason given")))
        if declined:
            # A notice, not an error: an error would undo the failed transaction, the note and the task for the
            # responsible that tell what happened.
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Not charged"),
                    'message': "\n".join(declined),
                    'type': 'danger',
                    'sticky': True,
                    'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
                },
            }
        return True

    def _charge(self, invoices):
        """One charge on the saved card for all ``invoices``. Returns the transaction, or None when not charged."""
        self.ensure_one()
        amount = self.currency_id.round(sum(invoices.mapped('amount_residual')))
        if self.currency_id.compare_amounts(amount, 0) <= 0:
            return None
        if self.max_amount and self.currency_id.compare_amounts(amount, self.max_amount) > 0:
            self._warn(_("Not charged: %(amount)s is more than the %(max)s per charge the customer agreed to.",
                         amount=self.currency_id.format(amount), max=self.currency_id.format(self.max_amount)))
            return None
        token = self.token_id.sudo()
        tx = self.env['payment.transaction'].sudo().create({
            'provider_id': token.provider_id.id,
            'payment_method_id': token.payment_method_id.id,
            'amount': amount,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
            'token_id': token.id,
            'operation': 'offline',
            'invoice_ids': [(6, 0, invoices.ids)],
            'xpago_domiciliation_id': self.id,
        })
        tx._send_payment_request()
        if tx.state == 'done':
            tx._post_process()
        if tx.state == 'error':
            self._warn(_("The card was declined for %(amount)s (%(invoices)s): %(reason)s",
                         amount=self.currency_id.format(amount), invoices=', '.join(invoices.mapped('name')),
                         reason=tx.state_message or _("no reason given")))
        else:
            self.message_post(body=_("Charged %(amount)s to %(card)s: %(invoices)s",
                                     amount=self.currency_id.format(amount), card=token.display_name,
                                     invoices=', '.join(invoices.mapped('name'))))
        return tx

    def _warn(self, message):
        self.ensure_one()
        self.message_post(body=message)
        if self.user_id and not self.activity_ids.filtered(lambda a: a.summary == message):
            self.activity_schedule('mail.mail_activity_data_todo', summary=message[:255], user_id=self.user_id.id)

    @api.model
    def _cron_charge(self):
        # Every company's customers, whoever runs the scheduled action.
        records = self.sudo().search([('state', '=', 'active'), ('source', '=', 'invoices'), ('schedule', '!=', 'manual')])
        for record in records:
            record = record.with_company(record.company_id)
            invoices = record._invoices_to_charge(automatic=True)
            if invoices:
                record._charge(invoices)
                if not modules.module.current_test:
                    self.env.cr.commit()  # One customer's charge is kept even if the next one fails.

    # === BUTTONS === #

    def action_pause(self):
        self.state = 'paused'

    def action_resume(self):
        self.state = 'active'

    def action_view_transactions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Charges"),
            'res_model': 'payment.transaction',
            'view_mode': 'list,form',
            'domain': [('xpago_domiciliation_id', '=', self.id)],
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Owed now"),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self._invoices_to_charge().ids)],
        }
