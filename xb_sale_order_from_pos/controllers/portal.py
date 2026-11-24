# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS
# «My layaway» / «My order»: the customer pays what they want on their layaway or order
# from its online page, within the terms (minimum payment, never more than the balance).
#
# Odoo 17's order page only pays the whole quotation (or its prepayment), never a
# chosen amount on a confirmed order. Odoo 17 does pay any amount on an order through
# its own payment link (Sales ▸ order ▸ Generate a Payment Link): that is the page an
# accepted amount is sent to, with the same access check the payment link uses.
from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.sale.controllers.portal import CustomerPortal


class XbLayawayPortal(CustomerPortal):

    @http.route()
    def portal_order_page(self, order_id, report_type=None, access_token=None, message=False,
                          download=False, payment_amount=None, **kw):
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
                if not error:
                    return request.redirect(order_sudo._xb_payment_link(amount))
        response = super().portal_order_page(
            order_id, report_type=report_type, access_token=access_token, message=message,
            download=download, **kw
        )
        if error and hasattr(response, "qcontext"):
            response.qcontext["xb_layaway_error"] = error
            response.qcontext["xb_layaway_amount"] = amount
        return response

