# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    xb_rawbt = fields.Boolean(
        string="Kiosk printer through RawBT",
        help="The kiosk prints its tickets through the RawBT app of the tablet (Android) "
             "on the printer RawBT is connected to (USB, Bluetooth or network), instead "
             "of the Epson ePOS printer.")
    xb_rawbt_paper = fields.Selection(
        [("384", "58 mm"), ("576", "80 mm")], string="Paper width",
        default="576", required=True)
    xb_rawbt_method = fields.Selection(
        [("intent", "Android intent"), ("scheme", "rawbt: link")],
        string="Sending method", default="intent", required=True,
        help="How the kiosk hands the ticket to RawBT. Use the test page to find the "
             "one that prints on your tablet.")
    xb_rawbt_test_url = fields.Char(
        string="Printer test page", compute="_compute_xb_rawbt_test_url")

    @api.depends("access_token")
    def _compute_xb_rawbt_test_url(self):
        base = self.get_base_url()
        for config in self:
            config.xb_rawbt_test_url = (
                "%s/xb_rawbt/test/%s?access_token=%s" % (base, config.id, config.access_token)
                if config.id and config.access_token else False)

    def _xb_rawbt_data(self):
        self.ensure_one()
        if not self.xb_rawbt:
            return False
        return {"width": int(self.xb_rawbt_paper or 576), "method": self.xb_rawbt_method or "intent"}

    @api.model
    def _load_pos_self_data_read(self, records, config):
        read_records = super()._load_pos_self_data_read(records, config)
        if read_records:
            read_records[0]["_xb_rawbt"] = config._xb_rawbt_data()
        return read_records
