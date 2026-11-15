import hmac

from odoo import http
from odoo.http import request


class PriceChecker(http.Controller):

    @staticmethod
    def _config(config_id, token):
        """The Point of Sale of this link, when ``token`` is its price checker key."""
        try:
            config = request.env['pos.config'].sudo().browse(int(config_id)).exists()
        except (TypeError, ValueError):
            return None
        if not config or not config.price_checker_token or not token \
                or not hmac.compare_digest(str(config.price_checker_token), str(token)):
            return None
        return config

    @http.route('/price-checker/<int:config_id>/<string:token>', type='http', auth='public', methods=['GET'])
    def page(self, config_id, token):
        config = self._config(config_id, token)
        if not config:
            raise request.not_found()
        request.update_context(lang=config._price_checker_lang())
        return request.render('xb_price_checker.page', {
            'config': config,
            'company': config.company_id,
            'token': token,
            'idle': max(config.price_checker_idle or 15, 3),
        })

    @http.route('/price-checker/lookup', type='jsonrpc', auth='public')
    def lookup(self, config_id, token, barcode):
        """The screen of the link (no user): the key of the link proves which store it is."""
        config = self._config(config_id, token)
        if not config:
            return {'found': False, 'error': 'not_found'}
        return config._price_checker_info(barcode)

    @http.route('/price-checker/lookup-user', type='jsonrpc', auth='user')
    def lookup_user(self, config_id, barcode, db=None):
        """An app with an Odoo session (the XPago terminal): the user must see that Point of Sale."""
        if db and db != request.db:
            return {'found': False, 'error': 'other_db'}
        try:
            config = request.env['pos.config'].browse(int(config_id)).exists()
        except (TypeError, ValueError):
            config = None
        if not config:
            return {'found': False, 'error': 'not_found'}
        if hasattr(config, 'check_access'):
            config.check_access('read')
        else:  # Odoo 17
            config.check_access_rights('read')
            config.check_access_rule('read')
        return config._price_checker_info(barcode)
