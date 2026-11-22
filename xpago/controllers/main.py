import json
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
                tx_sudo._record(tx_sudo._xpago_fetch_payment_data())
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
                tx_sudo._record(tx_sudo._xpago_fetch_card_data())
            except ValidationError:
                _logger.warning("XPago: could not read back %s on return; the scheduled action will.", tx_sudo.reference)
        return request.redirect('/payment/status')

    @http.route(const.NOTIFY_ROUTE, type='http', methods=['POST'], auth='public', csrf=False, save_session=False)
    def xpago_notify(self, **_kwargs):
        """XPago says a payment changed. Only a notice signed with the secret XPago gave this Odoo is heard, and even
        then it only says what to read again: what XPago answers when asked decides, as with the scheduled actions."""
        body = request.httprequest.get_data()
        headers = request.httprequest.headers
        provider_sudo = request.env['payment.provider'].sudo()._xpago_verify_notice(
            body, headers.get(const.NOTIFY_TIMESTAMP_HEADER), headers.get(const.NOTIFY_SIGNATURE_HEADER))
        if not provider_sudo:
            _logger.warning("XPago: notice refused, the signature does not match")
            return request.make_json_response({'error': 'invalid_signature'}, status=401)
        try:
            notice = json.loads(body)
        except ValueError:
            return request.make_json_response({'received': True})
        _logger.info("XPago notice %s: %s", notice.get('type') if isinstance(notice, dict) else None,
                     notice.get('object') if isinstance(notice, dict) else None)
        try:
            provider_sudo._xpago_handle_notice(notice)
        except Exception:  # noqa: BLE001 - XPago only needs to know it arrived; the scheduled actions read it too
            _logger.exception("XPago: could not handle the notice")
        return request.make_json_response({'received': True})
