# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _xb_kiosk_send_whatsapp(self, phone):
        return self._xb_send_wa_quotation(phone=phone)
