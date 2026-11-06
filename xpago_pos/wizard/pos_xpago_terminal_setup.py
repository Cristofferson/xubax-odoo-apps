from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PosXpagoTerminalSetup(models.TransientModel):
    """Which XPago terminal goes on which point of sale. It proposes, warns and only changes what is confirmed: a
    payment method is created only when asked for, with the journal the user chose."""
    _name = 'pos.xpago.terminal.setup'
    _description = "XPago terminals and points of sale"

    provider_id = fields.Many2one(
        'payment.provider', string="XPago account", required=True, domain="[('code', '=', 'xpago')]",
        default=lambda self: self.env['payment.provider'].search(
            [('code', '=', 'xpago'), ('company_id', 'in', self.env.company.parent_ids.ids)], order='company_id desc', limit=1),
    )
    journal_id = fields.Many2one(
        'account.journal', string="Journal for new terminals", domain="[('type', '=', 'bank')]",
        help="Only used for the payment methods this assistant creates (lines with «Create»).",
    )
    line_ids = fields.One2many('pos.xpago.terminal.setup.line', 'wizard_id', string="Points of sale")
    warning_html = fields.Html(compute='_compute_warning_html', sanitize=False)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if 'line_ids' not in fields_list:
            return values
        configs = self.env['pos.config'].search([('company_id', 'in', self.env.company.parent_ids.ids + self.env.company.child_ids.ids)])
        methods = self.env['pos.payment.method'].search([('use_payment_terminal', '=', 'xpago')])
        used = configs.payment_method_ids.filtered(lambda m: m.use_payment_terminal == 'xpago')
        free = list(methods - used)
        lines = []
        for config in configs:
            current = config.payment_method_ids.filtered(lambda m: m.use_payment_terminal == 'xpago')[:1]
            # A point of sale without a terminal is offered one of its company that nobody uses yet, each one once.
            proposed = current
            if not proposed:
                proposed = next((m for m in free if not m.company_id or m.company_id == config.company_id),
                                self.env['pos.payment.method'])
                if proposed:
                    free.remove(proposed)
            lines.append((0, 0, {'config_id': config.id, 'method_id': proposed.id}))
        values['line_ids'] = lines
        return values

    @api.depends('line_ids.method_id', 'line_ids.new_serial', 'line_ids.has_open_session')
    def _compute_warning_html(self):
        for wizard in self:
            by_serial = {}
            for line in wizard.line_ids:
                serial = line._serial()
                if serial:
                    by_serial.setdefault(serial, []).append(line.config_id.name)
            warnings = [
                _("Terminal %(serial)s would be on %(registers)s. A terminal shows one charge at a time: a new charge "
                  "replaces the one it was waiting for.", serial=serial, registers=', '.join(names))
                for serial, names in by_serial.items() if len(names) > 1
            ]
            open_names = wizard.line_ids.filtered('has_open_session').config_id.mapped('name')
            if open_names:
                warnings.append(_("These points of sale have a session open and are left as they are until it is "
                                  "closed: %s", ', '.join(open_names)))
            wizard.warning_html = Markup('').join(
                Markup('<div class="alert alert-warning mb-2" role="alert">%s</div>') % warning for warning in warnings
            ) if warnings else False

    def action_apply(self):
        self.ensure_one()
        if any(line.create_method and line.new_serial for line in self.line_ids) and not self.journal_id:
            raise UserError(_("Choose the journal for the new terminals before creating them."))
        Method = self.env['pos.payment.method']
        created = {}
        changed, skipped = [], []
        for line in self.line_ids:
            method = line.method_id
            serial = (line.new_serial or '').strip()
            if not method and serial and line.create_method:
                method = created.get(serial) or Method.search(
                    [('use_payment_terminal', '=', 'xpago'), ('xpago_terminal_serial', '=', serial)], limit=1)
                if not method:
                    method = Method.create({
                        'name': _("Card · XPago %s", serial),
                        'journal_id': self.journal_id.id,
                        'use_payment_terminal': 'xpago',
                        'xpago_provider_id': self.provider_id.id,
                        'xpago_terminal_serial': serial,
                        'company_id': line.config_id.company_id.id,
                    })
                created[serial] = method
            if not method:
                continue
            config = line.config_id
            current = config.payment_method_ids.filtered(lambda m: m.use_payment_terminal == 'xpago')
            if current == method:
                continue
            if line.has_open_session:
                skipped.append(config.name)
                continue
            config.payment_method_ids = [(3, other.id) for other in current - method] + [(4, method.id)]
            changed.append(config.name)
        message = _("Updated: %s.", ', '.join(changed)) if changed else _("Nothing to change.")
        if skipped:
            message += ' ' + _("Left as they were (session open): %s.", ', '.join(skipped))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _("XPago terminals"), 'message': message, 'type': 'warning' if skipped else 'success',
                       'next': {'type': 'ir.actions.act_window_close'}},
        }


class PosXpagoTerminalSetupLine(models.TransientModel):
    _name = 'pos.xpago.terminal.setup.line'
    _description = "XPago terminal of a point of sale"

    wizard_id = fields.Many2one('pos.xpago.terminal.setup', required=True, ondelete='cascade')
    config_id = fields.Many2one('pos.config', string="Point of sale", required=True, readonly=True)
    config_company_id = fields.Many2one(related='config_id.company_id')
    method_id = fields.Many2one(
        'pos.payment.method', string="XPago terminal",
        domain="[('use_payment_terminal', '=', 'xpago'), ('company_id', 'in', [config_company_id, False])]",
        help="The XPago terminal payment method this point of sale charges with. Empty: leave it as it is.",
    )
    terminal_serial = fields.Char(related='method_id.xpago_terminal_serial', string="S/N")
    new_serial = fields.Char(string="Or a new terminal (S/N)")
    create_method = fields.Boolean(string="Create", help="Create the payment method of this new terminal.")
    has_open_session = fields.Boolean(compute='_compute_has_open_session')

    @api.depends('config_id')
    def _compute_has_open_session(self):
        for line in self:
            line.has_open_session = bool(line.config_id.session_ids.filtered(lambda s: s.state != 'closed'))

    def _serial(self):
        self.ensure_one()
        return self.method_id.xpago_terminal_serial or (self.new_serial or '').strip() or False
