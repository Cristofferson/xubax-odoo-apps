import hmac
import time
from datetime import timedelta

from markupsafe import escape

from odoo import _, fields, http
from odoo.http import request

# Longest code accepted from a terminal: GS1 strings stay well under this.
MAX_BARCODE_LENGTH = 256


class XpagoReader(http.Controller):
    """The XPago terminal as a wireless barcode reader for other screens of the same Odoo.

    The Odoo app on the terminal calls these routes with the Odoo session of its built-in browser. It lists the
    registers and kiosks it can send to (``targets``) and sends each code it reads (``scan``):

    * a register (Point of Sale) gets it through the POS bus;
    * an attendance or self-order kiosk opens without a user and without the bus: it asks ``pull`` every few
      seconds, proving which kiosk it is with its own secret (the kiosk key, or the register's access token);
    * an Odoo screen in a computer's browser is paired with a QR (user menu) holding a random key made by that
      browser, which listens to its own bus channel.
    """

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _token(token):
        token = (token or '').strip()
        return token if 8 <= len(token) <= 64 and token.replace('-', '').isalnum() else ''

    @staticmethod
    def _other_db(db):
        # A code names its database: a terminal logged in under another address of the same Odoo may answer for it,
        # but never another Odoo with a register of the same number.
        return bool(db) and db != request.db

    @staticmethod
    def _channel(token):
        return f'xpago_reader_{token}'

    @staticmethod
    def _kiosk_channel(kind, record_id):
        return f'xpago_reader_{kind}_{record_id}'

    @staticmethod
    def _register_channel(config):
        return f'xpago_reader_pos_{config.id}_{config.access_token}'

    def _config(self, config_id):
        try:
            config = request.env['pos.config'].browse(int(config_id)).exists()
        except (TypeError, ValueError):
            return request.env['pos.config']
        if config:
            config.check_access_rights('read')
            config.check_access_rule('read')
        return config

    def _attendance_company(self, company_id):
        """A company of this user whose attendance kiosk may get the codes (Attendances installed)."""
        if 'attendance_kiosk_key' not in request.env['res.company']._fields:
            return request.env['res.company']
        try:
            company_id = int(company_id)
        except (TypeError, ValueError):
            return request.env['res.company']
        return request.env.user.company_ids.filtered(lambda c: c.id == company_id)

    def _send(self, channel, barcode, device, kind='xpago_reader_scan'):
        request.env['bus.bus'].sudo()._sendone(channel, kind, {'barcode': barcode, 'device': str(device)[:64]})

    # ------------------------------------------------------------------ routes for the terminal

    @http.route('/xpago/reader/targets', type='json', auth='user')
    def targets(self):
        """What this terminal may send to: registers, self-order kiosks and attendance kiosks of this user."""
        configs = request.env['pos.config'].search([])
        registers, kiosks = [], []
        for config in configs:
            entry = {'id': config.id, 'name': config.name, 'open': bool(config.current_session_id)}
            if 'self_ordering_mode' in config._fields and config.self_ordering_mode == 'kiosk':
                kiosks.append(entry)
            else:
                registers.append(entry)
        attendance = []
        if 'attendance_kiosk_key' in request.env['res.company']._fields:
            attendance = [{'id': c.id, 'name': c.name} for c in request.env.user.company_ids]
        return {'db': request.db, 'registers': registers, 'self_order': kiosks, 'attendance': attendance}

    @http.route('/xpago/reader/link', type='http', auth='user')
    def link(self, token=None, db=None, name=None, kind=None, **kwargs):
        # The pairing QR (computer screens) is a link so a phone camera lands on a page that explains it.
        body = _("This code links an XPago terminal to the Odoo screen open in your browser. "
                 "Scan it from the Odoo app on the terminal, in “Reader for the computer” mode.")
        return request.make_response(
            "<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
            f"<p style='font:18px sans-serif;padding:24px'>{escape(body)}</p>",
            headers=[('Content-Type', 'text/html; charset=utf-8')],
        )

    @http.route('/xpago/reader/pair', type='json', auth='user')
    def pair(self, config_id=None, token=None, db=None):
        if self._other_db(db):
            return {'ok': False, 'error': 'other_db'}
        if not config_id:
            if not self._token(token):
                return {'ok': False, 'error': 'not_found'}
            return {'ok': True, 'name': request.env.user.name, 'open': True, 'user': request.env.user.name,
                    'db': request.db}
        config = self._config(config_id)
        if not config:
            return {'ok': False, 'error': 'not_found'}
        return {'ok': True, 'name': config.name, 'open': bool(config.current_session_id),
                'user': request.env.user.name, 'db': request.db}

    @http.route('/xpago/reader/scan', type='json', auth='user')
    def scan(self, barcode, config_id=None, device='', token=None, db=None, kiosk=None, company_id=None):
        if self._other_db(db):
            return {'ok': False, 'error': 'other_db'}
        barcode = (barcode or '').strip()
        if not barcode or len(barcode) > MAX_BARCODE_LENGTH:
            return {'ok': False, 'error': 'bad_barcode'}
        if kiosk == 'attendance':
            company = self._attendance_company(company_id)
            if not company:
                return {'ok': False, 'error': 'not_found'}
            self._send(self._kiosk_channel('att', company.id), barcode, device)
            return {'ok': True, 'name': company.name, 'open': True}
        if kiosk == 'self_order':
            config = self._config(config_id)
            if not config:
                return {'ok': False, 'error': 'not_found'}
            self._send(self._kiosk_channel('so', config.id), barcode, device)
            # What the kiosk will add, so a terminal used by the customer can show it right away.
            return {'ok': True, 'name': config.name, 'open': bool(config.current_session_id),
                    'product': self._kiosk_product(config, barcode)}
        if not config_id:
            token = self._token(token)
            if not token:
                return {'ok': False, 'error': 'not_found'}
            self._send(self._channel(token), barcode, device)
            return {'ok': True, 'name': request.env.user.name, 'open': True}
        config = self._config(config_id)
        if not config:
            return {'ok': False, 'error': 'not_found'}
        # Odoo 17: the register listens to a channel named with its own secret (reader.js). Access was checked
        # above; sudo only to read that secret.
        self._send(self._register_channel(config.sudo()), barcode, device, 'XPAGO_READER_SCAN')
        return {'ok': True, 'name': config.name, 'open': bool(config.current_session_id)}

    # ------------------------------------------------------------------ route for the kiosks

    @http.route('/xpago/reader/pull', type='json', auth='public')
    def pull(self, kiosk=None, key=None, config_id=None, access_token=None, last=0):
        """Kiosks ask here every few seconds for the codes read on a terminal. ``last`` is the last notification
        they already got. They prove which kiosk they are with their own secret."""
        channel = None
        env = request.env(su=True)
        if kiosk == 'attendance' and key and 'attendance_kiosk_key' in env['res.company']._fields:
            company = env['res.company'].search([('attendance_kiosk_key', '=', str(key))], limit=1)
            if company:
                channel = self._kiosk_channel('att', company.id)
        elif kiosk == 'self_order' and config_id and access_token:
            try:
                config = env['pos.config'].browse(int(config_id)).exists()
            except (TypeError, ValueError):
                config = env['pos.config']
            if config and config.access_token and hmac.compare_digest(str(config.access_token), str(access_token)):
                channel = self._kiosk_channel('so', config.id)
        if not channel:
            return {'last': 0, 'codes': []}
        bus = env['bus.bus']
        if not last:
            # First call: start from now, never replay codes read before the kiosk opened.
            return {'last': bus._bus_last_id(), 'codes': []}
        notes = bus._poll([channel], int(last))
        codes = [n['message']['payload']['barcode'] for n in notes
                 if n['message'].get('type') == 'xpago_reader_scan' and n['message'].get('payload', {}).get('barcode')]
        return {'last': max([n['id'] for n in notes], default=int(last)), 'codes': codes}

    # ------------------------------------------------------------------ self-checkout (the customer holds the terminal)

    def _kiosk_product(self, config, barcode):
        """Name and price, as the kiosk shows them, of the product with this barcode; False if the kiosk has none."""
        product = request.env['product.product'].sudo().search(
            [('barcode', '=', barcode), ('available_in_pos', '=', True)], limit=1)
        if not product or ('self_order_available' in product._fields and not product.self_order_available):
            return False
        config = config.sudo()
        price = config.pricelist_id._get_product_price(product, 1.0) if config.pricelist_id else product.lst_price
        taxes = product.taxes_id.filtered(lambda t: t.company_id in config.company_id.parent_ids)
        if taxes:
            totals = taxes.compute_all(price, config.currency_id, 1.0, product=product)
            price = totals['total_included'] if config.iface_tax_included == 'total' else totals['total_excluded']
        return {'name': product.display_name, 'price': config.currency_id.round(price),
                'currency': config.currency_id.symbol}

    @http.route('/xpago/reader/charge', type='json', auth='user')
    def charge(self, config_id, after=0):
        """The card charge a self-order kiosk just sent to the terminal (newer than ``after``), so the terminal can
        bring the charge app to the front and know when it is paid."""
        config = self._config(config_id)
        if not config:
            return {}
        domain = [('config_id', '=', config.id), ('create_date', '>', fields.Datetime.now() - timedelta(minutes=10))]
        if after:
            domain.append(('id', '>', int(after)))
        charge = request.env['pos.xpago.charge'].sudo().search(domain, limit=1, order='id desc')
        if not charge:
            return {}
        return {'id': charge.id, 'state': charge.state, 'amount': charge.amount,
                'app_url': charge.terminal_app_url or False}

    # ------------------------------------------------------------------ the terminal opens its charge app by itself

    def _wake_methods(self, serial=None):
        """The XPago terminals of the companies of this user, by serial number."""
        domain = [('use_payment_terminal', '=', 'xpago'), ('company_id', 'in', request.env.user.company_ids.ids)]
        if serial:
            domain.append(('xpago_terminal_serial', '=ilike', serial.strip()))
        return request.env['pos.payment.method'].sudo().search(domain)

    @http.route('/xpago/reader/terminals', type='json', auth='user')
    def terminals(self):
        """The XPago terminals the Odoo app on a terminal can say it is, to open their charge app by itself."""
        out = {}
        for method in self._wake_methods():
            serial = (method.xpago_terminal_serial or '').strip().upper()
            if serial:
                entry = out.setdefault(serial, {'serial': serial, 'names': [], 'wake': False})
                entry['names'].append(method.name)
                entry['wake'] = entry['wake'] or method.xpago_wake_terminal
        return {'terminals': sorted(out.values(), key=lambda t: t['serial']), 'db': request.db}

    @http.route('/xpago/reader/wake', type='json', auth='user')
    def wake(self, serial, after=0):
        """The charge a point of sale just sent to the terminal ``serial`` (newer than ``after``), while one of its
        payment methods has «Open the charge app on the terminal». ``enabled`` False: the terminal may ask rarely."""
        methods = self._wake_methods(serial).filtered('xpago_wake_terminal')
        if not methods:
            return {'enabled': False}
        domain = [('payment_method_id', 'in', methods.ids), ('state', '=', 'pending'),
                  ('create_date', '>', fields.Datetime.now() - timedelta(minutes=10))]
        if after:
            domain.append(('id', '>', int(after)))
        charge = request.env['pos.xpago.charge'].sudo().search(domain, limit=1, order='id desc')
        if not charge or not charge.terminal_app_url:
            return {'enabled': True}
        return {'enabled': True, 'id': charge.id, 'amount': charge.amount, 'app_url': charge.terminal_app_url,
                'age': int((fields.Datetime.now() - charge.create_date).total_seconds())}

    @http.route('/xpago/reader/manager_pin', type='json', auth='user')
    def manager_pin(self, pin, config_id=None):
        """True when ``pin`` is the PIN of a manager: an employee of this company whose user manages the Point of
        Sale, or a manager of the kiosk's register (Point of Sale with employees). Five wrong tries wait a minute."""
        session = request.session
        tries = [t for t in session.get('xpago_pin_tries', []) if t > time.time() - 60]
        if len(tries) >= 5:
            return {'ok': False, 'error': 'wait'}
        pin = str(pin or '').strip()
        Employee = request.env['hr.employee'].sudo() if 'hr.employee' in request.env else None
        ok = False
        if pin and Employee is not None and 'pin' in Employee._fields:
            employees = Employee.search([('pin', '=', pin), ('company_id', 'in', request.env.user.company_ids.ids)])
            config = self._config(config_id) if config_id else None
            managers = config.sudo().advanced_employee_ids if config and 'advanced_employee_ids' in config._fields else Employee
            ok = any(e in managers or (e.user_id and e.user_id.has_group('point_of_sale.group_pos_manager'))
                     for e in employees)
        if not ok:
            session['xpago_pin_tries'] = tries + [time.time()]
        return {'ok': ok}
