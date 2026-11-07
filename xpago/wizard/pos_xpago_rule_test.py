from markupsafe import Markup

from odoo import _, api, fields, models


class PosXpagoRuleTest(models.TransientModel):
    """Tries the payment rules on a real sale: which months it would offer and where its money would go."""

    _name = 'pos.xpago.rule.test'
    _description = "Try the XPago payment rules"

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    pos_order_id = fields.Many2one('pos.order', string="Point of sale order")
    channel = fields.Selection([('pos', "Point of sale"), ('kiosk', "Kiosk")], default='pos', required=True)
    split = fields.Boolean(string="Split the charge", help="As a point of sale that splits the charge would.")
    result = fields.Html(compute='_compute_result', sanitize=False)

    @api.depends('pos_order_id', 'channel', 'split')
    def _compute_result(self):
        Rule = self.env['payment.xpago.rule']
        for wizard in self:
            order = wizard.pos_order_id
            if not order:
                wizard.result = Markup('<p class="text-muted">%s</p>') % _("Choose an order to see how it would be charged.")
                continue
            parts = Rule._xpago_plan(order.company_id, wizard.channel, Rule._xpago_lines_from_records(order.lines),
                                     order.amount_total, config=order.config_id, date=order.date_order.date(),
                                     split=wizard.split)
            by_terminal, single, as_account = _("By the terminal"), _("Single payment"), _("As the account offers")
            rows = Markup('')
            for part in parts:
                terms = part['terms']
                months = single if terms == [1] else (', '.join(str(t) for t in terms if t > 1) if terms else as_account)
                rows += Markup('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>') % (
                    order.currency_id.format(part['amount']),
                    part['account'].name or by_terminal,
                    months,
                    ', '.join(part['rules'].mapped('name')) or '—',
                )
            wizard.result = Markup('<table class="table table-sm"><thead><tr><th>%s</th><th>%s</th><th>%s</th><th>%s</th>'
                                   '</tr></thead><tbody>%s</tbody></table>') % (
                _("Charge"), _("Deposit account"), _("Months without interest"), _("Rules applied"), rows)
