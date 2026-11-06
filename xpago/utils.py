from odoo.tools import float_repr


def xpago_amount(currency, amount):
    """`amount` rounded to the currency, as the number XPago's API expects (Odoo 17's rounding can leave
    1111.1100000000001, which must not reach the API)."""
    return float(float_repr(currency.round(amount), currency.decimal_places))
