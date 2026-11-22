from odoo.addons.web.controllers.webmanifest import WebManifest

# The calculator installs as its own app («Instalar app»): on a phone or a computer as a web app, and on an XPago
# terminal the terminal app gives it its own «Calculadora» icon.
CALCULATOR = 'xpago_calculator'


class XpagoWebManifest(WebManifest):

    def _get_scoped_app_name(self, app_id):
        if app_id == CALCULATOR:
            return 'Calculadora'
        return super()._get_scoped_app_name(app_id)

    def _get_scoped_app_icons(self, app_id):
        if app_id == CALCULATOR:
            return [{'src': '/xpago/static/src/img/calculator_terminal.png', 'sizes': '256x256', 'type': 'image/png'}]
        return super()._get_scoped_app_icons(app_id)
