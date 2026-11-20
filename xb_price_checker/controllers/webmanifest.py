from odoo.addons.web.controllers.webmanifest import WebManifest

# «Install as an app» of the price checker: its own name and icon on the device's screen.
APP_ID = 'xb_price_checker'


class PriceCheckerWebManifest(WebManifest):

    def _get_scoped_app_name(self, app_id):
        if app_id == APP_ID:
            return 'Verificador de precios'
        return super()._get_scoped_app_name(app_id)

    def _get_scoped_app_icons(self, app_id):
        if app_id == APP_ID:
            return [{'src': '/xb_price_checker/static/description/icon.png', 'sizes': '256x256', 'type': 'image/png'}]
        return super()._get_scoped_app_icons(app_id)
