# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS - CFDI 4.0 (Mexico)
from odoo import models


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        # FormaPago: report on the CFDI how the order was actually paid, mapped from
        # the dominant POS payment method (cash 01, transfer 03, credit 04, debit
        # 28...). Without l10n_mx_edi_pos the move would otherwise fall back to the
        # journal/partner default. Only for our orders on a Mexican company; skipped
        # when none of the methods carry a SAT mapping or the partner already pins
        # its own forma de pago.
        if self._xb_has_our_so() and self._xb_is_mx():
            payments = self.payment_ids.filtered(
                lambda p: p.payment_method_id.l10n_mx_edi_payment_method_id
            )
            if payments and not self.partner_id.l10n_mx_edi_payment_method_id:
                dominant = max(payments, key=lambda p: abs(p.amount))
                vals["l10n_mx_edi_payment_method_id"] = (
                    dominant.payment_method_id.l10n_mx_edi_payment_method_id.id
                )
        return vals
