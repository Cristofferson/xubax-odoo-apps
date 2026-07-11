# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def _load_pos_data_models(self, config):
        data = super()._load_pos_data_models(config)
        return data + ['xb.delivery.account']

    def close_session_from_ui(self, bank_payment_method_diff_pairs=None):
        result = super().close_session_from_ui(bank_payment_method_diff_pairs)
        # Take the store offline on every platform when the session closes.
        for account in self.config_id.xb_delivery_account_ids.filtered(
                lambda a: a.state == 'connected'):
            try:
                account.sudo()._get_driver().set_store_status(False)
                account._log('out', 'store_status', success=True,
                             message='offline (session closed)')
            except Exception as exc:  # noqa: BLE001 - never block closing
                _logger.warning(
                    'xb_delivery: could not set %s offline on close: %s',
                    account.name, exc)
                account._log('out', 'store_status', success=False, message=str(exc))
        return result
