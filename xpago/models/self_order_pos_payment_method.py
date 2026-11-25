from odoo import _, models
from odoo.exceptions import UserError


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _payment_request_from_kiosk(self, order):
        """Send the order's amount to the terminal beside the kiosk. The charge pays the order by itself once the
        card is approved, and the kiosk hears it through its payment status channel."""
        if self.payment_provider == 'xpago_spei':
            # The CLABE is made out to who pays: the kiosk asks for them first (see _xpago_kiosk_transfer).
            raise UserError(_("A transfer at the kiosk needs who pays: name, phone and email."))
        if self.payment_provider != 'xpago':
            return super()._payment_request_from_kiosk(order)
        provider = self.sudo().xpago_provider_id
        account = self._xpago_kiosk_account(order, provider)
        charge = self.env['pos.xpago.charge'].sudo()._xpago_create(
            self.sudo(), provider, order.amount_total, order.session_id, order.uuid, order=order, account=account)
        return {'xpago_charge_id': charge.id, 'state': charge.state}

    def _xpago_kiosk_account(self, order, provider):
        """The account of the XPago payment rules of what the customer ordered."""
        Rule = self.env['payment.xpago.rule'].sudo()
        plan = Rule._xpago_plan(order.company_id, 'kiosk', Rule._xpago_lines_from_records(order.sudo().lines),
                                order.amount_total, config=order.config_id, invoiced=bool(order.to_invoice))
        return plan[0]['account'] if provider._xpago_bank_account_id(plan[0]['account']) else \
            self.sudo()._xpago_charge_account(provider)

    def _xpago_kiosk_transfer(self, order, customer):
        """The CLABE of a kiosk order. A CLABE of this order still waiting for the same amount is shown again (the
        customer may be paying it right now); money that already arrived pays the order."""
        self.ensure_one()
        if self.payment_provider != 'xpago_spei':
            raise UserError(_("This payment method does not take XPago transfers."))
        provider = self.sudo().xpago_provider_id
        if not provider.active:
            raise UserError(_("XPago is disabled. An administrator can enable it in the XPago payment provider."))
        Transfer = self.env['pos.xpago.transfer'].sudo()
        currency = order.currency_id
        mine = Transfer.search([('payment_method_id', '=', self.id), ('pos_order_id', '=', order.id),
                                ('state', 'in', ('awaiting', 'paid'))], order='id desc', limit=10)
        mine._xpago_refresh()
        mine._xpago_complete_kiosk_orders()
        same = mine.filtered(lambda t: not currency.compare_amounts(t.amount, order.amount_total))
        reuse = same.filtered(lambda t: t.state == 'paid')[:1] or same.filtered(lambda t: t.state == 'awaiting')[:1]
        if reuse:
            return reuse
        transfer = Transfer._xpago_create(
            self.sudo(), provider, order.amount_total, order.session_id, order.uuid,
            self._xpago_transfer_customer(customer or {}), account=self._xpago_kiosk_account(order, provider))
        transfer.pos_order_id = order.id
        transfer._xpago_complete_kiosk_orders()  # a transfer can be paid the moment it is read back
        return transfer
