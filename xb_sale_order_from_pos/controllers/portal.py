# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS
# «My layaway»: the customer pays what they want on their layaway from its online
# page, within the terms (minimum payment, never more than the balance).
from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.sale.controllers.portal import CustomerPortal


class XbLayawayPortal(CustomerPortal):

    @http.route()
    def portal_order_page(self, order_id, report_type=None, access_token=None, message=False,
                          download=False, payment_amount=None, amount_selection=None, **kw):
        error = False
        amount = self._cast_as_float(payment_amount)
        if amount and not report_type:
            try:
                order_sudo = self._document_check_access("sale.order", order_id, access_token=access_token)
            except (AccessError, MissingError):
                order_sudo = None
            ours = order_sudo and (
                (order_sudo.xb_so_kind == "layaway" and order_sudo.xb_layaway_state != "draft")
                or (order_sudo.xb_so_kind in ("order", "order_layaway") and order_sudo.state == "sale")
            )
            if ours:
                error = order_sudo._xb_layaway_check_payment(amount)
                if error:
                    payment_amount = None
        response = super().portal_order_page(
            order_id, report_type=report_type, access_token=access_token, message=message,
            download=download, payment_amount=payment_amount, amount_selection=amount_selection, **kw
        )
        if error and hasattr(response, "qcontext"):
            response.qcontext["xb_layaway_error"] = error
            response.qcontext["xb_layaway_amount"] = amount
        return response
