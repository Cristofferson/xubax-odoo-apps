# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class PosConfig(models.Model):
    _inherit = "pos.config"

    xb_va_wa_send_template_id = fields.Many2one(
        "whatsapp.template", string="WhatsApp template to send the selection",
        domain="[('model', '=', 'xb.va.conversation'), ('status', '=', 'approved')]",
        help="Approved template about a virtual seller conversation, with the selection page link.")
    xb_va_create_lead = fields.Boolean(
        "Create an opportunity in CRM", default=True,
        help="When the customer asks for the selection, a CRM opportunity is created with the conversation.")

    def action_xb_va_create_wa_template(self):
        """A draft template ready to submit to Meta, with the right variables."""
        self.ensure_one()
        account = self.env["whatsapp.account"].search(
            [("allowed_company_ids", "in", self.company_id.id)], limit=1) or self.env["whatsapp.account"].search([], limit=1)
        if not account:
            raise UserError(_("Set up a WhatsApp account first."))
        lang = (self.company_id.partner_id.lang or "en_US")
        spanish = lang.startswith("es")
        body = ("Hola, soy {{1}} de {{2}}. Aquí tienes lo que vimos juntos en el kiosco y toda nuestra "
                "conversación: {{3}}\nCuando quieras, te esperamos.") if spanish else (
                "Hi, I'm {{1}} from {{2}}. Here is what we looked at together at the kiosk and our whole "
                "conversation: {{3}}\nWe'll be happy to see you again.")
        codes = dict(self.env["whatsapp.template"]._fields["lang_code"].selection)
        lang_code = next((c for c in (lang, lang[:2]) if c in codes), "en")
        template = self.env["whatsapp.template"].create({
            "name": _("Virtual seller: your selection"),
            "template_name": "virtual_seller_selection_%s" % self.id,
            "wa_account_id": account.id,
            "model_id": self.env["ir.model"]._get_id("xb.va.conversation"),
            "lang_code": lang_code,
            "template_type": "utility",
            "body": body,
            "variable_ids": [
                (0, 0, {"name": "{{1}}", "line_type": "body", "field_type": "field",
                        "field_name": "config_id.xb_va_name", "demo_value": self.xb_va_name or "Sofía"}),
                (0, 0, {"name": "{{2}}", "line_type": "body", "field_type": "field",
                        "field_name": "company_id.name", "demo_value": self.company_id.name}),
                (0, 0, {"name": "{{3}}", "line_type": "body", "field_type": "field",
                        "field_name": "share_url", "demo_value": "%s/xb-va/s/example" % self.get_base_url()}),
            ],
        })
        return {"type": "ir.actions.act_window", "res_model": "whatsapp.template", "res_id": template.id,
                "view_mode": "form", "target": "current"}
