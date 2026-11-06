from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.xpago import const


class PaymentXpagoInstallmentRule(models.Model):
    _name = 'payment.xpago.installment.rule'
    _description = "XPago: months without interest by amount"
    _order = 'provider_id, min_amount'

    provider_id = fields.Many2one('payment.provider', required=True, ondelete='cascade', index=True)
    currency_id = fields.Many2one(related='provider_id.main_currency_id')
    min_amount = fields.Monetary(
        string="Sale from", required=True, default=0.0,
        help="The rule applies to sales of this amount or more, up to the next rule.",
    )
    terms = fields.Char(
        string="Months offered",
        help="Months without interest separated by commas, for example \"3, 6, 12\". Leave it empty to offer the "
             "single payment only.",
    )

    _provider_min_amount_unique = models.Constraint(
        'unique(provider_id, min_amount)', "There is already a rule from this amount.",
    )

    def _parse_terms(self):
        self.ensure_one()
        terms = []
        for part in (self.terms or '').replace(';', ',').split(','):
            part = part.strip()
            if not part:
                continue
            if not part.isdigit() or not 2 <= int(part) <= const.MAX_TERMS:
                raise ValidationError(_(
                    "Write the months as whole numbers from 2 to %(max)s separated by commas, for example \"3, 6, 12\".",
                    max=const.MAX_TERMS,
                ))
            terms.append(int(part))
        return sorted(set(terms))

    @api.constrains('terms', 'min_amount')
    def _check_terms(self):
        for rule in self:
            if rule.min_amount < 0:
                raise ValidationError(_("The amount of a rule cannot be negative."))
            rule._parse_terms()
