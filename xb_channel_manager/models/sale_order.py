# -*- coding: utf-8 -*-
from odoo import api, fields, models


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
