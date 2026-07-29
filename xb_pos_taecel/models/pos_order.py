# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _

from .. import const

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _xb_taecel_account(self):
        """The TAECEL account serving this order's POS, if any.

        Resolved through ``_serving_domain`` -- the very same rule the POS
        loader uses to decide which account to offer the cashier. When the two
        disagreed, the register happily sold a recharge the back end then
        refused to dispatch: money taken, nothing delivered, no error.

        The account owned by the order's company wins; otherwise the account
        that company was explicitly added to (``shared_company_ids``), which is
        how a group funds one single TAECEL account for several companies.
        """
        self.ensure_one()
        Account = self.env['xb.taecel.account']
        # sudo: the business rule lives in the domain. Reading through record
        # rules on top of it could silently drop the account the cashier was
        # just allowed to sell on -- and a missing account here means a paid,
        # undelivered recharge.
        candidates = Account.sudo().search(
            Account._serving_domain(self.config_id, self.company_id))
        own = candidates.filtered(lambda a: a.company_id == self.company_id)
        return (own or candidates)[:1]

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
        Product = self.env['xb.taecel.product']
        created = Txn.browse()
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
                # The register sends the code, which is what dispatch needs;
                # point at the catalog record too, so the back office reads
                # "Telcel $ 50.00" instead of an empty cell. Unique per
                # (code, account), and free-amount carriers simply have none.
                # Archived products count: TAECEL retires codes and the sync
                # deactivates rather than deletes them, precisely so that what
                # was sold keeps pointing at what it was.
                product = Product.sudo().with_context(active_test=False).search([
                    ('account_id', '=', account.id),
                    ('code', '=', line.taecel_product_code),
                ], limit=1) if line.taecel_product_code else Product
                created |= Txn.create({
                    'account_id': account.id,
                    'carrier_id': line.taecel_carrier_id.id or False,
                    'product_id': product.id or False,
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
        if created:
            self._xb_wake_dispatcher()
        return True

    @api.model
    def _xb_wake_dispatcher(self):
        """Ask the dispatcher cron to run now instead of at its next turn.

        Dispatch stays out of the checkout on purpose: TAECEL is allowed up to
        60 seconds to answer, and no cashier is going to hold a customer for
        that. But leaving the recharge to the cron's own schedule adds a wait
        of its own -- a minute nominally, longer where one cron thread serves
        many databases -- and that delay is dead time in which the customer
        walks away before a rejection can be caught.

        ``_trigger`` costs one row and a NOTIFY: the register is not kept
        waiting, and the recharge leaves within seconds. Failure to wake the
        cron is not an error worth losing the sale over -- the scheduled run
        picks the transaction up anyway -- so it is logged, not raised.
        """
        cron = self.env.ref('xb_pos_taecel.cron_taecel_dispatch',
                            raise_if_not_found=False)
        if not cron:
            return False
        try:
            cron.sudo()._trigger()
        except Exception:  # noqa: BLE001 - never let this break a paid order
            _logger.exception('TAECEL: could not wake the dispatch cron.')
            return False
        return True
