# -*- coding: utf-8 -*-
"""A sale made by an affiliate, as TAECEL reports it in getSales.

This is a mirror, not a ledger: the rows belong to TAECEL and are re-read, so
the model stores them keyed by TransID and updates in place. That keeps the
pull idempotent -- re-running a day never duplicates -- and lets a sale that
was still 'En proceso' when first seen settle later without a second record.
"""
import logging

import pytz

from odoo import api, fields, models

from odoo.addons.xb_pos_taecel import const
from odoo.addons.xb_pos_taecel.models.pos_compat import HAS_MODEL_CONSTRAINT
from odoo.addons.xb_pos_taecel.models.xb_taecel_account import _money

_logger = logging.getLogger(__name__)

#: getSales pays a commission per row. Not in the base module's key list
#: because the POS never reads it -- only a distributor measuring a network
#: cares what each sale actually earned.
K_SALE_COMMISSION = 'Comision'

#: TAECEL stamps every sale in **Mexico City local time** -- verified against a
#: dispatch we had timed independently (20:06 UTC came back as 14:06). An Odoo
#: Datetime is UTC, so storing the string raw shifts the whole network report
#: by six hours. TAECEL serves Mexico only, so this is the right zone to read
#: its clock in, regardless of where the Odoo user sits.
TAECEL_TZ = 'America/Mexico_City'


class XbTaecelAffiliateSale(models.Model):
    _name = 'xb.taecel.affiliate.sale'
    _description = 'TAECEL Affiliate Sale'
    _order = 'date desc, id desc'

    affiliate_id = fields.Many2one(
        'xb.taecel.affiliate', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='affiliate_id.company_id', store=True)
    currency_id = fields.Many2one(related='affiliate_id.currency_id')

    trans_id = fields.Char(string='TransID', required=True, index=True)
    date = fields.Datetime(readonly=True)
    carrier = fields.Char(readonly=True)
    reference = fields.Char(string='Phone / Reference', readonly=True)
    folio = fields.Char(readonly=True)
    bolsa_id = fields.Char(string='Wallet', readonly=True)
    amount = fields.Monetary(readonly=True)
    commission = fields.Monetary(
        readonly=True, help='What TAECEL paid the affiliate on this sale.')
    final_balance = fields.Monetary(
        string='Balance After', readonly=True,
        help='The affiliate wallet balance TAECEL reported after this sale.')
    note = fields.Char(readonly=True)

    status = fields.Selection([
        ('ok', 'Successful'),
        ('ko', 'Failed'),
        ('pending', 'In Progress'),
    ], readonly=True, index=True)

    if HAS_MODEL_CONSTRAINT:
        _txn_affiliate_uniq = models.Constraint(
            'unique(trans_id, affiliate_id)',
            "This transaction is already recorded for the affiliate.",
        )
    else:
        _sql_constraints = [
            ('txn_affiliate_uniq', 'unique(trans_id, affiliate_id)',
             "This transaction is already recorded for the affiliate."),
        ]

    @api.depends('carrier', 'amount', 'currency_id')
    def _compute_display_name(self):
        for sale in self:
            sale.display_name = '%s %s' % (
                sale.carrier or '',
                sale.currency_id.format(sale.amount) if sale.currency_id
                else sale.amount)

    @api.model
    def _date_of(self, row):
        """TAECEL's ``Fecha`` as UTC, which is what an Odoo Datetime holds.

        Stored raw it would read six hours early and every "today" filter and
        daily total in the network report would be wrong near the day
        boundary. An unparseable stamp is dropped rather than guessed: a sale
        with no date is still a sale, a sale with an invented one is a lie.
        """
        raw = str(row.get(const.K_SALE_DATE) or '').strip()
        if not raw:
            return False
        try:
            naive = fields.Datetime.to_datetime(raw)
        except (ValueError, TypeError):
            _logger.info('TAECEL: unreadable sale date %r', raw)
            return False
        if not naive:
            return False
        return pytz.timezone(TAECEL_TZ).localize(naive).astimezone(
            pytz.utc).replace(tzinfo=None)

    @api.model
    def _status_of(self, row):
        """Normalise TAECEL's Status text.

        It arrives as free text and TAECEL pads 'Fracasada ' with a trailing
        space, so compare on a stripped, lowered copy rather than equality.
        """
        raw = str(row.get(const.K_SALE_STATUS) or '').strip().lower()
        if raw.startswith(const.SALE_STATUS_OK):
            return 'ok'
        if raw.startswith(const.SALE_STATUS_KO):
            return 'ko'
        return 'pending'

    @api.model
    def _absorb(self, affiliate, bolsa_id, rows):
        """Create or update the affiliate's sales from getSales rows.

        Returns how many rows were taken in. Existing rows are written rather
        than skipped: a sale first seen 'En proceso' settles on a later pull.
        """
        count = 0
        for row in rows or []:
            trans_id = str(row.get(const.K_SALE_TRANS_ID) or '').strip()
            if not trans_id:
                continue
            values = {
                'affiliate_id': affiliate.id,
                'trans_id': trans_id,
                'date': self._date_of(row),
                'carrier': row.get(const.K_SALE_CARRIER) or '',
                'reference': row.get(const.K_SALE_PHONE) or '',
                'folio': row.get(const.K_SALE_FOLIO) or '',
                'bolsa_id': str(bolsa_id),
                'amount': _money(row.get(const.K_SALE_AMOUNT)),
                'commission': _money(row.get(K_SALE_COMMISSION)),
                'final_balance': _money(row.get(const.K_SALE_FINAL_BALANCE)),
                'note': row.get(const.K_SALE_NOTE) or '',
                'status': self._status_of(row),
            }
            existing = self.search([
                ('affiliate_id', '=', affiliate.id),
                ('trans_id', '=', trans_id),
            ], limit=1)
            if existing:
                existing.write(values)
            else:
                self.create(values)
            count += 1
        return count
