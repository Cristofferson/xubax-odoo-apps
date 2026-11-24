# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS
# «My layaway»: the customer pays what they want on their layaway from its online
# page, within the terms (minimum payment, never more than the balance).
#
# Odoo 18: the sale portal only offers payment on quotations (state draft/sent). For our
# confirmed layaways and orders the chosen amount is checked here and Odoo's own payment
# form (payment.form) is rendered on «My layaway» / «My order» for that amount; the
# transaction route then refuses any other amount on those orders.
from odoo import _, http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request

from odoo.addons.sale.controllers.portal import CustomerPortal, PaymentPortal


def _xb_cast_float(value):
    try:
        return float(value) if value not in (None, False, "") else None
    except (TypeError, ValueError):
        return None


def _xb_is_ours(order_sudo):
    """Our layaways / orders that take payments of any amount from their page."""
    return bool(order_sudo) and (
        (order_sudo.xb_so_kind == "layaway" and order_sudo.xb_layaway_state not in (False, "draft"))
        or (order_sudo.xb_so_kind in ("order", "order_layaway") and order_sudo.state == "sale")
    )


class XbLayawayPortal(CustomerPortal):

    @http.route()
    def portal_order_page(self, order_id, report_type=None, access_token=None, message=False,
                          download=False, payment_amount=None, **kw):
        error = False
        pay_amount = False
        order_sudo = None
        amount = _xb_cast_float(payment_amount)
        if amount and not report_type:
            try:
                order_sudo = self._document_check_access("sale.order", order_id, access_token=access_token)
            except (AccessError, MissingError):
                order_sudo = None
            if _xb_is_ours(order_sudo):
                error = order_sudo._xb_layaway_check_payment(amount)
                if not error:
                    pay_amount = amount
        response = super().portal_order_page(
            order_id, report_type=report_type, access_token=access_token, message=message,
            download=download, **kw
        )
        if hasattr(response, "qcontext"):
            if error:
                response.qcontext["xb_layaway_error"] = error
                response.qcontext["xb_layaway_amount"] = amount
            elif pay_amount:
                values = self._get_payment_values(order_sudo)
                values["amount"] = pay_amount
                response.qcontext.update(values)
                response.qcontext["xb_pay_amount"] = pay_amount
        return response


class XbLayawayPaymentPortal(PaymentPortal):

    @http.route()
    def portal_order_transaction(self, order_id, access_token, **kwargs):
        # The amount comes from the page: on our layaways / orders, never accept one
        # outside the terms (minimum payment, never more than the balance).
        try:
            order_sudo = self._document_check_access("sale.order", order_id, access_token)
        except (AccessError, MissingError):
            order_sudo = None
        if _xb_is_ours(order_sudo):
            amount = _xb_cast_float(kwargs.get("amount"))
            error = order_sudo._xb_layaway_check_payment(amount or 0.0)
            if error:
                raise ValidationError(error or _("The amount is not valid."))
        return super().portal_order_transaction(order_id, access_token, **kwargs)
