# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models

from .pos_compat import HAS_MODEL_CONSTRAINT

from .. import const

_logger = logging.getLogger(__name__)

RECENT_SALES_DAYS = 90


class XbTaecelCarrier(models.Model):
    """A TAECEL carrier (Telcel, Movistar, CFE, a giftcard brand...).

    The carrier decides how the POS behaves for its products:

    * ``carrier_type`` catalog -> show the fixed-amount products as buttons;
      free -> show one numeric field for the cashier to type the amount.
    * ``field_*`` mirror the carrier's single ``Campos`` entry so the POS can
      validate what the cashier types (phone number, account, bill reference)
      *before* charging the customer -- length, format, required.

    Synced from getProducts. Deactivated, never deleted, when TAECEL drops it,
    because past transactions and products point here.
    """
    _name = 'xb.taecel.carrier'
    _description = 'Recharge Carrier'
    _order = 'bolsa_id, name'
    _inherit = ['pos.load.mixin']

    account_id = fields.Many2one(
        'xb.taecel.account', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='account_id.company_id', store=True)

    carrier_uid = fields.Char(
        required=True, index=True, help='Carrier ID in the provider catalog.')
    name = fields.Char(required=True)
    logo_url = fields.Char()
    bolsa_id = fields.Char(help='Wallet this carrier is charged against.')
    category = fields.Char()
    category_uid = fields.Char()
    carrier_type = fields.Selection([
        (const.CARRIER_CATALOG, 'Catalog (fixed amounts)'),
        (const.CARRIER_FREE, 'Free amount'),
    ], default=const.CARRIER_CATALOG)
    active = fields.Boolean(default=True)
    currency_id = fields.Many2one(related='account_id.currency_id')

    # -- What a bill payment costs, and who keeps each part ------------------
    # The provider charges the account a fixed amount on every bill payment
    # (CargoTrans; $5 on most services), on top of the bill, and pays no
    # commission on them. Selling a bill at its face value therefore loses that
    # charge: the customer pays it as the service cost (which, on accounts of
    # the XPago network, already carries the XPago fee), plus whatever the
    # business adds for itself.
    provider_fee = fields.Monetary(
        string='Provider Charge', readonly=True,
        help='Fixed amount the provider takes from your wallet on every payment, '
             'on top of the bill. Read from the catalog.')
    provider_fee_list = fields.Monetary(
        string='Provider List Charge', readonly=True,
        help="The provider's standard charge. When your charge is higher, the "
             'difference goes to your distributor (it already includes the XPago fee).')
    provider_client_fee = fields.Monetary(
        string='Provider Customer Fee', readonly=True,
        help='Fee the provider itself asks to charge the customer. Read from the catalog.')
    provider_commission = fields.Float(
        string='Provider Commission (%)', readonly=True,
        help='What the provider pays you on each sale of this carrier (gift cards).')
    is_bill_payment = fields.Boolean(
        string='Bill Payment', compute='_compute_is_bill_payment', store=True,
        help='A service payment (light, water, TV...). Gift cards and airtime are not.')
    merchant_fee = fields.Monetary(
        string='My Fee',
        help='What you add on top for each payment. It is all yours and is kept '
             'when the catalog is synchronized. Empty: the account default.')
    xpago_fee = fields.Monetary(
        string='XPago Fee', compute='_compute_customer_fee', store=True,
        help='XPago fee on each bill payment. The customer pays it inside the '
             'service cost; it is never shown as a line of its own.')
    fee_provider_part = fields.Monetary(
        string='Service Cost', compute='_compute_customer_fee', store=True,
        help='What the customer pays for the service, on top of the amount.')
    fee_merchant_part = fields.Monetary(
        string='Business Fee', compute='_compute_customer_fee', store=True,
        help='Part of the customer fee that is yours.')
    customer_fee = fields.Monetary(
        string='Customer Fee', compute='_compute_customer_fee', store=True,
        help='Everything the customer pays on top of the amount: the service '
             'cost and your fee. Shown on the receipt.')

    @api.depends('bolsa_id', 'category', 'provider_fee')
    def _compute_is_bill_payment(self):
        for carrier in self:
            carrier.is_bill_payment = (carrier.bolsa_id == const.BOLSA_SERVICES
                                       and 'gift' not in (carrier.category or '').lower())

    @api.depends('provider_fee', 'provider_fee_list', 'provider_client_fee', 'merchant_fee', 'is_bill_payment',
                 'account_id.xpago_fee', 'account_id.merchant_fee')
    def _compute_customer_fee(self):
        for carrier in self:
            xpago = carrier.account_id.xpago_fee if carrier.is_bill_payment else 0.0
            # Part of the XPago fee the provider already collects through a higher charge.
            collected = min(max(carrier.provider_fee - carrier.provider_fee_list, 0.0), xpago) \
                if carrier.provider_fee_list else 0.0
            mine = carrier.merchant_fee if carrier.merchant_fee else (
                carrier.account_id.merchant_fee if carrier.is_bill_payment else 0.0)
            carrier.xpago_fee = xpago
            # The customer sees one service cost: the provider part with the XPago fee inside it.
            carrier.fee_provider_part = carrier.provider_fee + carrier.provider_client_fee - collected + xpago
            carrier.fee_merchant_part = mine
            carrier.customer_fee = carrier.fee_provider_part + mine

    product_ids = fields.One2many('xb.taecel.product', 'carrier_id')
    product_count = fields.Integer(compute='_compute_product_count')
    recent_sale_count = fields.Integer(
        string='Recent Sales', compute='_compute_recent_sale_count',
        help='Successful sales in the last 90 days. The register lists the '
             'most sold carriers first.')

    # -- Input field spec (the carrier's single Campos entry) --------------
    field_label = fields.Char(help='What the cashier is asked for, e.g. "Numero Celular".')
    field_key = fields.Char(help='Parameter name the provider expects, e.g. "referencia".')
    field_min = fields.Integer(help='Minimum length of the reference.')
    field_max = fields.Integer(help='Maximum length of the reference.')
    field_format = fields.Selection([
        (const.FORMATO_NUMERIC, 'Numeric'),
        (const.FORMATO_ALPHANUM, 'Alphanumeric'),
        (const.FORMATO_EMAIL, 'Email'),
    ], default=const.FORMATO_NUMERIC)
    field_required = fields.Boolean(default=True)
    field_confirm = fields.Boolean(
        string='Confirm Reference',
        help='The provider asks the cashier to type the reference twice.')

    # Odoo 19 dropped _sql_constraints in favour of models.Constraint;
    # Odoo 18 has no models.Constraint. Declaring the wrong one is a
    # silent no-op, so pick at import time (see pos_compat).
    if HAS_MODEL_CONSTRAINT:
        _carrier_account_uniq = models.Constraint(
            'unique(carrier_uid, account_id)',
            "This carrier already exists for the account.",
        )
    else:
        _sql_constraints = [
            ('carrier_account_uniq', 'unique(carrier_uid, account_id)',
             "This carrier already exists for the account."),
        ]

    @api.depends('product_ids')
    def _compute_product_count(self):
        for carrier in self:
            carrier.product_count = len(carrier.product_ids)

    def _compute_recent_sale_count(self):
        counts = {}
        if self.ids:
            since = fields.Datetime.now() - timedelta(days=RECENT_SALES_DAYS)
            groups = self.env['xb.taecel.transaction'].sudo()._read_group(
                [('carrier_id', 'in', self.ids), ('state', '=', const.STATE_DONE),
                 ('create_date', '>=', since)],
                ['carrier_id'], ['__count'])
            counts = {carrier.id: count for carrier, count in groups}
        for carrier in self:
            carrier.recent_sale_count = counts.get(carrier.id, 0)

    # -- Sync --------------------------------------------------------------
    @api.model
    def _sync_from_taecel(self, account, carriers):
        """Upsert carriers from a getProducts ``data.carriers`` list.

        Returns {carrier_uid: record} so the product sync can link products to
        their carrier without a second query.
        """
        by_uid = {}
        for row in carriers or []:
            uid = str(row.get(const.K_CARRIER_ID) or '').strip()
            if not uid:
                continue
            values = self._values_from_payload(account, row)
            existing = self.with_context(active_test=False).search([
                ('account_id', '=', account.id), ('carrier_uid', '=', uid),
            ], limit=1)
            if existing:
                existing.write(dict(values, active=True))
                by_uid[uid] = existing
            else:
                by_uid[uid] = self.create(values)
        return by_uid

    @api.model
    def _values_from_payload(self, account, row):
        campos = row.get(const.K_CARRIER_FIELDS) or []
        field = campos[0] if campos else {}
        comision = row.get('Comision') or {}

        def number(key):
            try:
                return float(comision.get(key) or 0.0)
            except (TypeError, ValueError):
                return 0.0
        # TipoCargo / TipoAbono: 1 = percent, 2 = fixed amount. Only a fixed
        # charge can be passed on to the customer as a fee.
        fixed = str(comision.get('TipoCargo') or '') == const.COMMISSION_FIXED
        if not fixed and number('CargoTrans'):
            _logger.warning('TAECEL: carrier %s has a percent charge; not passed on to the customer.',
                            row.get(const.K_CARRIER_NAME))
        return {
            'provider_fee': number('CargoTrans') if fixed else 0.0,
            'provider_fee_list': number('def_CargoTrans') if fixed else 0.0,
            'provider_client_fee': number('ComisionCliente'),
            'provider_commission': number('AbonoTrans')
            if str(comision.get('TipoAbono') or '') == const.COMMISSION_PERCENT else 0.0,
            'account_id': account.id,
            'carrier_uid': str(row.get(const.K_CARRIER_ID) or '').strip(),
            'name': row.get(const.K_CARRIER_NAME) or '',
            'logo_url': row.get(const.K_CARRIER_LOGO) or '',
            'bolsa_id': str(row.get(const.K_CARRIER_BOLSA) or ''),
            'category': row.get(const.K_CARRIER_CATEG) or '',
            'category_uid': str(row.get(const.K_CARRIER_CATEG_ID) or ''),
            'carrier_type': str(row.get(const.K_CARRIER_TYPE) or const.CARRIER_CATALOG),
            'field_label': field.get(const.K_FIELD_NAME) or '',
            'field_key': field.get(const.K_FIELD_KEY) or 'referencia',
            'field_min': int(field.get(const.K_FIELD_MIN) or 0),
            'field_max': int(field.get(const.K_FIELD_MAX) or 0),
            'field_format': str(field.get(const.K_FIELD_FORMAT) or const.FORMATO_NUMERIC),
            'field_required': str(field.get(const.K_FIELD_REQUIRED) or '1') == '1',
            'field_confirm': str(field.get(const.K_FIELD_CONFIRM) or '0') == '1',
        }

    # -- POS ---------------------------------------------------------------
    @api.model
    def _load_pos_data_domain(self, data, config=None):
        return [('active', '=', True)]

    @api.model
    def _load_pos_data_fields(self, config=None):
        return ['id', 'carrier_uid', 'name', 'logo_url', 'bolsa_id', 'category',
                'category_uid', 'carrier_type', 'customer_fee', 'provider_fee', 'xpago_fee',
                'fee_provider_part', 'fee_merchant_part', 'is_bill_payment', 'field_label',
                'field_key', 'field_min', 'field_max', 'field_format',
                'field_required', 'field_confirm', 'account_id', 'currency_id',
                'recent_sale_count']
