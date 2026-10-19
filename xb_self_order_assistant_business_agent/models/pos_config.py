# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    xb_va_ba_kb_source = fields.Selection([
        ("own", "Only what I write here"),
        ("agent", "The WhatsApp agent's knowledge base"),
        ("both", "Both"),
    ], string="Shop knowledge from", default="own", required=True)
    xb_va_ba_account_id = fields.Many2one(
        "whatsapp.account", string="WhatsApp agent number",
        help="The seller uses the same knowledge base as this number's AI agent.")

    @api.onchange("xb_va_ba_kb_source")
    def _onchange_xb_va_ba_kb_source(self):
        if self.xb_va_ba_kb_source != "own" and not self.xb_va_ba_account_id:
            self.xb_va_ba_account_id = self.env["whatsapp.account"].search([("xb_ba_enabled", "=", True)], limit=1)

    def _xb_va_knowledge_text(self):
        own = super()._xb_va_knowledge_text()
        if self.xb_va_ba_kb_source == "own" or not self.xb_va_ba_account_id:
            return own
        account = self.xb_va_ba_account_id.sudo()
        kb = self.env["xb.business.knowledge"].sudo().search([
            "|", ("account_ids", "=", False), ("account_ids", "in", account.ids)])
        shared = kb._xb_as_text() if kb else ""
        if self.xb_va_ba_kb_source == "agent":
            return shared
        return "\n\n".join(t for t in (own, shared) if t)
