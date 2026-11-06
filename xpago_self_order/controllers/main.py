from werkzeug.exceptions import Unauthorized

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
