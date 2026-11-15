# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    cm_reservation_id = fields.Many2one(
        "xb.cm.reservation", string="OTA reservation", readonly=True,
        copy=False, index="btree_not_null")
    cm_channel_id = fields.Many2one(
        related="cm_reservation_id.channel_id", string="OTA channel")
    cm_commission_amount = fields.Monetary(
        string="Platform commission", currency_field="currency_id",
        copy=False,
        help="Commission kept by the platform, in the order currency.")
    cm_net_amount = fields.Monetary(
        string="Net income", currency_field="currency_id",
        compute="_compute_cm_net_amount", store=True,
        help="Order total minus the platform commission.")

    @api.depends("amount_total", "cm_commission_amount")
    def _compute_cm_net_amount(self):
        for order in self:
            order.cm_net_amount = order.amount_total - (
                order.cm_commission_amount or 0.0)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    cm_checkin = fields.Date(
        string="Check-in", copy=False, index=True,
        help="Arrival date of the stay. With the dates set, the line "
             "occupies the room on the channels every night until the "
             "check-out (not included).")
    cm_checkout = fields.Date(string="Check-out", copy=False, index=True)
    cm_nights = fields.Integer(
        string="Stay nights", compute="_compute_cm_nights")

    @api.depends("cm_checkin", "cm_checkout")
    def _compute_cm_nights(self):
        for line in self:
            line.cm_nights = ((line.cm_checkout - line.cm_checkin).days
                              if line.cm_checkin and line.cm_checkout
                              else 0)

    @api.constrains("cm_checkin", "cm_checkout")
    def _check_cm_dates(self):
        for line in self:
            if line.cm_checkin and line.cm_checkout and \
                    line.cm_checkout <= line.cm_checkin:
                raise ValidationError(_(
                    "The check-out must be after the check-in (%s).",
                    line.product_id.display_name))
