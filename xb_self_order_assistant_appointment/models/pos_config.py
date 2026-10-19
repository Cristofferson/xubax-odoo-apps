# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    xb_va_appointment_type_id = fields.Many2one(
        "appointment.type", string="Appointments the seller books",
        help="Empty = the seller does not book appointments.")
