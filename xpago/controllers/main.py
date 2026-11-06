import pprint

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.payment.logging import get_payment_logger
from odoo.addons.xpago import const

_logger = get_payment_logger(__name__)


class XpagoController(http.Controller):

    @http.route(const.PAYMENT_RETURN_ROUTE, type='http', methods=['GET'], auth='public')
    def xpago_return_from_checkout(self, **data):
        """The customer is back from XPago's checkout. The query string proves nothing: the transaction is updated
        from what XPago answers when asked."""
        _logger.info("Handling redirection from XPago with data:\n%s", pprint.pformat(data))
        tx_sudo = request.env['payment.transaction'].sudo()._search_by_reference('xpago', data)
        if tx_sudo and (not data.get('id') or not tx_sudo.provider_reference or tx_sudo.provider_reference == data['id']):
            try:
                tx_sudo._process('xpago', tx_sudo._xpago_fetch_payment_data())
            except ValidationError:
                _logger.warning("XPago: could not read back %s on return; the scheduled action will.", tx_sudo.reference)
        return request.redirect('/payment/status')

    @http.route(const.CARD_RETURN_ROUTE, type='http', methods=['GET'], auth='public')
    def xpago_return_from_card_checkout(self, **data):
        """The customer is back from saving the card. The query string proves nothing: the transaction is updated
        from what XPago answers when asked."""
        _logger.info("Handling redirection from the XPago card checkout with data:\n%s", pprint.pformat(data))
        tx_sudo = request.env['payment.transaction'].sudo().search([
            ('provider_code', '=', 'xpago'), ('reference', '=', data.get('reference') or ''),
            ('xpago_card_id', '=', data.get('id') or ''),
        ], limit=1)
        if tx_sudo:
            try:
                tx_sudo._process('xpago', tx_sudo._xpago_fetch_card_data())
            except ValidationError:
                _logger.warning("XPago: could not read back %s on return; the scheduled action will.", tx_sudo.reference)
        return request.redirect('/payment/status')
