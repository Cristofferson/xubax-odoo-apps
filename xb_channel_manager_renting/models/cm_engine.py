# -*- coding: utf-8 -*-
"""Stays as rental order lines: pickup / return dates, units, rental
pricing. Front-desk rental orders also occupy the rooms."""
from datetime import datetime, time

from odoo import api, models


class CmEngineRenting(models.AbstractModel):
    _inherit = "xb.cm.engine"

    @api.model
    def _stay_lines(self, order):
        return order.order_line.filtered(
            lambda l: l.is_rental or (l.cm_checkin and l.cm_checkout))

    @api.model
    def _line_dates(self, line):
        if line.is_rental and line.start_date and line.return_date:
            return line.start_date.date(), line.return_date.date()
        return super()._line_dates(line)

    @api.model
    def _line_units(self, line):
        if line.is_rental:
            return int(line.product_uom_qty or 1)
        return super()._line_units(line)

    @api.model
    def _stay_lines_domain(self, tmpl, date_from, date_to):
        rental = [
            ("product_template_id", "=", tmpl.id),
            ("is_rental", "=", True),
            ("start_date", "<", datetime.combine(date_to, time.max)),
            ("return_date", ">", datetime.combine(date_from, time.min)),
        ]
        base = super()._stay_lines_domain(tmpl, date_from, date_to)
        # A OR B in prefix notation (same syntax in Odoo 17 to 20)
        return (["|"] + ["&"] * (len(rental) - 1) + rental
                + ["&"] * (len(base) - 1) + base)

    @api.model
    def _stay_line_vals(self, tmpl, checkin, checkout, start_dt, return_dt):
        vals = super()._stay_line_vals(
            tmpl, checkin, checkout, start_dt, return_dt)
        vals.pop("name", None)  # the rental description shows the period
        vals.update({
            "is_rental": True,
            "start_date": start_dt,
            "return_date": return_dt,
        })
        return vals

    @api.model
    def _stay_order_vals(self, start_dt, return_dt):
        vals = super()._stay_order_vals(start_dt, return_dt)
        vals.update({
            "is_rental_order": True,
            "rental_start_date": start_dt,
            "rental_return_date": return_dt,
        })
        return vals

    @api.model
    def _stay_computed_price(self, listing, checkin, checkout):
        return None  # the rental pricing engine prices the period

    @api.model
    def _stay_set_period(self, order, line, checkin, checkout, start_dt,
                         return_dt):
        if not line.is_rental:
            return super()._stay_set_period(
                order, line, checkin, checkout, start_dt, return_dt)
        order.write({"rental_start_date": start_dt,
                     "rental_return_date": return_dt})
        line.write({"start_date": start_dt, "return_date": return_dt,
                    "cm_checkin": checkin, "cm_checkout": checkout})

    @api.model
    def _stay_set_product(self, line, tmpl):
        was_rental = line.is_rental
        super()._stay_set_product(line, tmpl)
        if was_rental:
            # changing the product drops the rental flag
            line.write({"is_rental": True})
