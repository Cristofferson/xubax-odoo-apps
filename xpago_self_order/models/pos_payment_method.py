from odoo import api, models
from odoo.fields import Domain


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _payment_request_from_kiosk(self, order):
        """Send the order's amount to the terminal beside the kiosk. The charge pays the order by itself once the
        card is approved, and the kiosk hears it through its payment status channel."""
        if self.use_payment_terminal != 'xpago':
            return super()._payment_request_from_kiosk(order)
        provider = self.sudo().xpago_provider_id
        # The account of the XPago payment rules of what the customer ordered, else the terminal's account.
        Rule = self.env['payment.xpago.rule'].sudo()
        plan = Rule._xpago_plan(order.company_id, 'kiosk', Rule._xpago_lines_from_records(order.sudo().lines),
                                order.amount_total, config=order.config_id)
        account = plan[0]['account'] if provider._xpago_bank_account_id(plan[0]['account']) else \
            self.sudo()._xpago_charge_account(provider)
        charge = self.env['pos.xpago.charge'].sudo()._xpago_create(
            self.sudo(), provider, order.amount_total, order.session_id, order.uuid, order=order, account=account)
        return {'xpago_charge_id': charge.id, 'state': charge.state}

    @api.model
    def _load_pos_self_data_domain(self, data, config):
        domain = super()._load_pos_self_data_domain(data, config)
        if config.self_ordering_mode == 'kiosk':
            domain = Domain.OR([
                [('use_payment_terminal', '=', 'xpago'), ('id', 'in', config.payment_method_ids.ids)],
                domain,
            ])
        return domain
