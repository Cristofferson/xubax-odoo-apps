# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # The SAT «Forma de pago» of the POS payment methods moved to the
    # xb_sale_order_from_pos_l10n_mx bridge, so the module no longer needs the Mexican
    # localisation. Hand the field over to the bridge instead of letting this upgrade
    # drop its column: the mapping each payment method carries is kept and the bridge
    # takes it back when it is installed. Its form view goes away here (it names the
    # field) and the bridge brings its own.
    cr.execute(
        """
        UPDATE ir_model_data
           SET module = 'xb_sale_order_from_pos_l10n_mx'
         WHERE module = 'xb_sale_order_from_pos'
           AND model = 'ir.model.fields'
           AND name = 'field_pos_payment_method__l10n_mx_edi_payment_method_id'
        """
    )
    moved = cr.rowcount
    cr.execute(
        """
        DELETE FROM ir_ui_view v
         USING ir_model_data d
         WHERE d.module = 'xb_sale_order_from_pos'
           AND d.name = 'xb_pos_payment_method_view_form'
           AND d.model = 'ir.ui.view'
           AND v.id = d.res_id
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'xb_sale_order_from_pos'
           AND name = 'xb_pos_payment_method_view_form'
        """
    )
    _logger.info("[XB-MIG 19.0.1.2.0] SAT forma de pago handed to xb_sale_order_from_pos_l10n_mx (%s field)", moved)
