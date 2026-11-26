from werkzeug.exceptions import BadRequest, NotFound, Unauthorized

from odoo import http

from odoo.addons.pos_self_order.controllers.orders import PosSelfOrderController


class PosSelfOrderXpagoController(PosSelfOrderController):

    def _xpago_kiosk_charge(self, access_token, order_id, charge_id):
        pos_config = self._verify_pos_config(access_token)
        charge = pos_config.env['pos.xpago.charge'].sudo().search([
            ('id', '=', int(charge_id)), ('pos_order_id', '=', int(order_id)), ('config_id', '=', pos_config.id),
        ], limit=1)
        if not charge:
            raise Unauthorized()
        return charge

    @http.route('/pos-self-order/xpago-charge-status/', auth='public', type='jsonrpc', website=True)
    def xpago_charge_status(self, access_token, order_id, charge_id):
        """Asked by the kiosk while the customer pays: reading the charge back also pays the order."""
        charge = self._xpago_kiosk_charge(access_token, order_id, charge_id)
        charge._xpago_refresh()
        view = charge._xpago_public_view()
        return {'state': view['state'], 'expires_at': view['expires_at']}

    @http.route('/pos-self-order/xpago-cancel-charge/', auth='public', type='jsonrpc', website=True)
    def xpago_cancel_charge(self, access_token, order_id, charge_id):
        charge = self._xpago_kiosk_charge(access_token, order_id, charge_id)
        charge._xpago_cancel()
        return {'state': charge.state}

    # === TRANSFER (SPEI) AT THE KIOSK === #

    def _xpago_kiosk_transfer_record(self, access_token, order_id, transfer_id):
        pos_config = self._verify_pos_config(access_token)
        transfer = pos_config.env['pos.xpago.transfer'].sudo().search([
            ('id', '=', int(transfer_id)), ('pos_order_id', '=', int(order_id)),
            ('pos_order_id.config_id', '=', pos_config.id),
        ], limit=1)
        if not transfer:
            raise Unauthorized()
        return transfer

    @staticmethod
    def _xpago_kiosk_transfer_view(transfer):
        """What the kiosk shows of the CLABE: no customer data goes back to the screen."""
        view = transfer._xpago_public_view()
        return {key: view[key] for key in ('id', 'state', 'amount', 'amount_received', 'amount_due', 'clabe',
                                           'clabe_last4', 'bank', 'beneficiary', 'business', 'concept',
                                           'checkout_url', 'expires_at')}

    @http.route('/pos-self-order/xpago-transfer-start/', auth='public', type='jsonrpc', website=True)
    def xpago_transfer_start(self, access_token, order, payment_method_id, customer):
        """The kiosk's «Pay by transfer»: the order is saved as the kiosk saves it to pay, then its CLABE is made out
        to who pays."""
        pos_config = self._verify_pos_config(access_token)
        results = self.process_order(order, access_token, None, 'kiosk')
        if not results['pos.order'][0].get('id'):
            raise BadRequest("Something went wrong")
        order_sudo = pos_config.env['pos.order'].browse(results['pos.order'][0]['id'])
        method = pos_config.env['pos.payment.method'].browse(int(payment_method_id))
        if not order_sudo or not method or method not in order_sudo.config_id.payment_method_ids \
                or method.use_payment_terminal != 'xpago_spei':
            raise NotFound("Order or payment method not found")
        transfer = method.sudo()._xpago_kiosk_transfer(order_sudo, customer if isinstance(customer, dict) else {})
        return {
            'order': order_sudo.read(order_sudo._load_pos_data_fields(pos_config.id), load=False),
            'transfer': self._xpago_kiosk_transfer_view(transfer),
        }

    @http.route('/pos-self-order/xpago-transfer-status/', auth='public', type='jsonrpc', website=True)
    def xpago_transfer_status(self, access_token, order_id, transfer_id):
        """Asked by the kiosk while the customer transfers: reading the transfer back also pays the order."""
        transfer = self._xpago_kiosk_transfer_record(access_token, order_id, transfer_id)
        transfer._xpago_refresh()
        transfer._xpago_complete_kiosk_orders()
        return self._xpago_kiosk_transfer_view(transfer)

    @http.route('/pos-self-order/xpago-transfer-cancel/', auth='public', type='jsonrpc', website=True)
    def xpago_transfer_cancel(self, access_token, order_id, transfer_id):
        transfer = self._xpago_kiosk_transfer_record(access_token, order_id, transfer_id)
        transfer._xpago_cancel()
        return {'state': transfer.state}
