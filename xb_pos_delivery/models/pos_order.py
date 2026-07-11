# -*- coding: utf-8 -*-
import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .. import const

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    xb_delivery_account_id = fields.Many2one(
        'xb.delivery.account', string='Delivery Account', index=True, copy=False)
    xb_delivery_provider = fields.Selection(
        related='xb_delivery_account_id.provider', store=True,
        string='Delivery Platform')
    xb_delivery_identifier = fields.Char(
        string='Platform Order ID', copy=False, index=True)
    xb_delivery_display_id = fields.Char(string='Platform Display ID', copy=False)
    xb_delivery_status = fields.Selection(
        const.DELIVERY_STATUSES, string='Delivery Status', copy=False)
    xb_delivery_type = fields.Selection(
        const.DELIVERY_TYPES, string='Fulfillment', copy=False)
    xb_prep_time = fields.Integer(string='Prep Time (min)', copy=False)
    xb_delivery_json = fields.Json(string='Platform Payload', copy=False)
    xb_courier_json = fields.Json(string='Courier Info', copy=False)
    xb_cash_due = fields.Monetary(
        string='Cash to Collect', copy=False, currency_field='currency_id',
        help='Cash the customer pays on a cash order (Mexico).')

    @api.ondelete(at_uninstall=False)
    def _xb_unlink_except_delivery(self):
        if self.filtered('xb_delivery_identifier'):
            raise UserError(_(
                'Delivery platform orders cannot be deleted. Reject or cancel '
                'them instead.'))

    @api.model
    def _load_pos_data_fields(self, config):
        # Core returns [] for pos.order, which means "load every field" —
        # our xb_* fields are included automatically. Only append when some
        # other module restricted the list (a non-empty list would otherwise
        # drop core fields like 'lines' from the POS model schema).
        fields_ = super()._load_pos_data_fields(config)
        if fields_:
            fields_ += [
                'xb_delivery_account_id', 'xb_delivery_provider',
                'xb_delivery_identifier', 'xb_delivery_display_id',
                'xb_delivery_status', 'xb_delivery_type', 'xb_prep_time',
                'xb_courier_json', 'xb_cash_due',
            ]
        return fields_

    # ------------------------------------------------------------------
    # Lifecycle actions (backend buttons + POS UI via data.call)
    # ------------------------------------------------------------------

    def _xb_check_delivery(self):
        self.ensure_one()
        if not self.xb_delivery_account_id:
            raise UserError(_('This is not a delivery platform order.'))

    def _xb_set_status(self, status):
        """Move the normalized status forward (never backwards)."""
        for order in self:
            current = const.STATUS_SEQUENCE.get(order.xb_delivery_status, 0)
            if const.STATUS_SEQUENCE[status] > current:
                order.xb_delivery_status = status
        return True

    def action_xb_accept(self, prep_time=None):
        self._xb_check_delivery()
        if self.xb_delivery_status not in (False, 'placed'):
            return True
        account = self.xb_delivery_account_id.sudo()
        if prep_time:
            self.xb_prep_time = prep_time
        try:
            account._get_driver().accept_order(self)
        except Exception as exc:  # noqa: BLE001
            account._log('out', 'accept_order', success=False, message=str(exc))
            raise UserError(_('The platform rejected the acceptance:\n%s', exc)) from exc
        self._xb_set_status('accepted')
        account._log('out', 'accept_order', success=True,
                     message=self.xb_delivery_identifier)
        account._bus_order_event(self)
        return True

    def action_xb_reject(self, reason=None):
        self._xb_check_delivery()
        account = self.xb_delivery_account_id.sudo()
        try:
            account._get_driver().deny_order(self, reason or _('Rejected by the restaurant'))
        except Exception as exc:  # noqa: BLE001
            account._log('out', 'deny_order', success=False, message=str(exc))
            raise UserError(_('The platform rejected the cancellation:\n%s', exc)) from exc
        self._xb_cancel_locally()
        account._log('out', 'deny_order', success=True,
                     message=self.xb_delivery_identifier)
        account._bus_order_event(self)
        return True

    def action_xb_ready(self):
        self._xb_check_delivery()
        account = self.xb_delivery_account_id.sudo()
        try:
            account._get_driver().mark_ready(self)
        except Exception as exc:  # noqa: BLE001
            # Not all platforms/fulfillments support a "ready" signal: log only.
            account._log('out', 'mark_ready', success=False, message=str(exc))
        self._xb_set_status('ready')
        if self.state == 'draft':
            self._xb_register_payment()
        account._log('out', 'mark_ready', success=True,
                     message=self.xb_delivery_identifier)
        account._bus_order_event(self)
        return True

    def _xb_register_payment(self):
        """Register the platform payment (or cash on pickup cash orders)."""
        self.ensure_one()
        account = self.xb_delivery_account_id.sudo()
        if self.xb_cash_due and self.xb_delivery_type == 'pickup':
            # The store collects the cash itself: use the session cash method.
            cash_method = self.config_id.payment_method_ids.filtered(
                lambda m: m.type == 'cash')[:1]
            if cash_method:
                self.env['pos.make.payment'].sudo().with_context(
                    active_ids=[self.id], active_id=self.id).create({
                        'amount': self.amount_total,
                        'payment_method_id': cash_method.id,
                    }).check()
                return
        account._register_order_payment(self)

    def _xb_cancel_locally(self):
        """Mark the order cancelled without touching the platform."""
        for order in self:
            order._xb_set_status('cancelled')
            if order.state == 'draft':
                order.state = 'cancel'
            else:
                _logger.warning(
                    'xb_delivery: order %s cancelled by platform after payment; '
                    'manual review needed.', order.pos_reference)
                order.message_post(body=_(
                    'The platform cancelled this order after it was paid. '
                    'Review the session payments.'))
        return True

    def action_xb_open_platform_payload(self):
        self._xb_check_delivery()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Platform Payload'),
            'res_model': 'pos.order',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('xb_pos_delivery.pos_order_view_form_xb_payload').id,
            'target': 'new',
        }

    def get_xb_courier_info(self):
        self.ensure_one()
        if not self.xb_courier_json:
            return {}
        data = self.xb_courier_json
        return json.loads(data) if isinstance(data, str) else data
