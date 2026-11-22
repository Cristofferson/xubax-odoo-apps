from odoo import _, api, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    @api.model
    def xpago_calculator_info(self):
        """What the calculator needs: whether it may charge, and on which terminals of the current company."""
        company = self.env.company
        can_charge = company.xpago_calculator_charge and self.env.user.has_group('point_of_sale.group_pos_user')
        terminals = self.search([
            ('use_payment_terminal', '=', 'xpago'),
            ('company_id', 'in', [company.id, False]),
        ]) if can_charge else self.browse()
        currency = company.currency_id
        return {
            'currency': {'symbol': currency.symbol, 'position': currency.position, 'digits': currency.decimal_places},
            'charge': bool(terminals),
            'terminals': [{
                'id': method.id,
                'name': method._xpago_calculator_label(),
                'serial': method.xpago_terminal_serial or '',
                'open_app': method.xpago_open_terminal_app,
                'timeout': method.xpago_card_timeout or 0,
            } for method in terminals],
        }

    def _xpago_calculator_label(self):
        """How the calculator names a terminal: the registers that use it and the end of its serial number, since
        two terminals often share a payment method name («Tarjeta»)."""
        self.ensure_one()
        configs = self.env['pos.config'].sudo().search([('payment_method_ids', 'in', self.ids)])
        where = ', '.join(configs.mapped('name')) or self.name
        serial = (self.xpago_terminal_serial or '').strip()
        return _("%(where)s · terminal …%(end)s", where=where, end=serial[-4:]) if serial else where
