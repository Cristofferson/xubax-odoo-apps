# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

from .pos_compat import HAS_MODEL_CONSTRAINT

from .. import const

_logger = logging.getLogger(__name__)


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
    _description = 'TAECEL Carrier'
    _order = 'bolsa_id, name'
    _inherit = ['pos.load.mixin']

    account_id = fields.Many2one(
        'xb.taecel.account', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='account_id.company_id', store=True)

    carrier_uid = fields.Char(
        required=True, index=True, help='Carrier ID in the TAECEL catalog.')
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
    customer_fee = fields.Monetary(
        string='Customer Fee',
        help='Fee charged to the customer on top of the amount (TAECEL '
             'ComisionCliente). Typically 0 for airtime; set for services.')
    currency_id = fields.Many2one(related='account_id.currency_id')

    product_ids = fields.One2many('xb.taecel.product', 'carrier_id')
    product_count = fields.Integer(compute='_compute_product_count')

    # -- Input field spec (the carrier's single Campos entry) --------------
    field_label = fields.Char(help='What the cashier is asked for, e.g. "Numero Celular".')
    field_key = fields.Char(help='Parameter name TAECEL expects, e.g. "referencia".')
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
        help='TAECEL asks the cashier to type the reference twice.')

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
        try:
            fee = float(comision.get('ComisionCliente') or 0.0)
        except (TypeError, ValueError):
            fee = 0.0
        return {
            'customer_fee': fee,
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
                'category_uid', 'carrier_type', 'customer_fee', 'field_label',
                'field_key', 'field_min', 'field_max', 'field_format',
                'field_required', 'field_confirm', 'account_id', 'currency_id']
