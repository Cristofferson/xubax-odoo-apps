# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _

from .. import const

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _xb_taecel_account(self):
        """The TAECEL account serving this order's POS, if any.

        The account owned by the order's company wins. Failing that, any
        active account that serves this register is used: the POS front end
        offers accounts without filtering by company (see
        ``_load_pos_data_domain``), so a register whose company owns no
        account of its own can legitimately sell on a single parent account
        -- one distributor account serving several companies of the same
        group. Refusing here would take the customer's money and never
        dispatch the recharge, which is exactly what happened before.
        """
        self.ensure_one()
        Account = self.env['xb.taecel.account']
        serves_this_pos = ['|', ('config_ids', '=', False),
                           ('config_ids', 'in', self.config_id.ids)]
        own = Account.search(
            [('active', '=', True), ('company_id', '=', self.company_id.id)]
            + serves_this_pos, limit=1)
        return own or Account.search(
            [('active', '=', True)] + serves_this_pos, limit=1)

    def _process_order(self, order, existing_order):
        """After the core saves the order, materialise its TAECEL transactions.

        Hooked here rather than in ``sync_from_ui`` because ``_process_order``
        returns the order id on both Odoo 18 and 19, whereas the wrapper's
        return shape differs. By this point the order and its lines are in the
        database.
        """
        order_id = super()._process_order(order, existing_order)
        self.browse(order_id)._xb_create_taecel_transactions()
        return order_id

    def _xb_create_taecel_transactions(self):
        """One transaction per TAECEL line, once the order is paid.

        Idempotent, and only for finalised orders: a draft save must not spawn
        transactions for a sale that might still change. Transactions are left
        in ``draft`` -- dispatching them needs the transactional API TAECEL has
        not documented yet. When it lands, this is the single place that calls
        ``txn.action_dispatch()``.
        """
        Txn = self.env['xb.taecel.transaction']
        for order in self:
            if order.state not in ('paid', 'done', 'invoiced'):
                continue
            account = order._xb_taecel_account()
            for line in order.lines.filtered('taecel_is_taecel'):
                if line.taecel_transaction_ids:
                    continue  # never duplicate on a re-save
                if not account:
                    _logger.warning(
                        'TAECEL line on order %s but no TAECEL account for its POS.',
                        order.name)
                    continue
                fee = line.taecel_fee
                Txn.create({
                    'account_id': account.id,
                    'carrier_id': line.taecel_carrier_id.id or False,
                    'product_code': line.taecel_product_code,
                    'bolsa_id': line.taecel_bolsa_id,
                    'reference': line.taecel_reference or '',
                    'amount': line.price_subtotal_incl - fee,
                    'customer_fee': fee,
                    'pos_order_id': order.id,
                    'pos_order_line_id': line.id,
                    'pos_session_id': order.session_id.id,
                    'user_id': order.user_id.id or self.env.uid,
                    'state': const.STATE_DRAFT,
                })
        return True
